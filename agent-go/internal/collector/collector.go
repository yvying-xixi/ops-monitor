// Package collector 采集系统指标、资产、系统信息与服务状态。
//
// 字段命名与 Python 版 Agent 保持一致，确保后端无需区分实现。
package collector

import (
	"os"
	"strings"

	"github.com/shirou/gopsutil/v4/cpu"
	"github.com/shirou/gopsutil/v4/disk"
	"github.com/shirou/gopsutil/v4/host"
	"github.com/shirou/gopsutil/v4/load"
	"github.com/shirou/gopsutil/v4/mem"
	"github.com/shirou/gopsutil/v4/net"
)

// DiskAsset 磁盘资产。
type DiskAsset struct {
	DeviceName string `json:"device_name"`
	MountPoint string `json:"mount_point"`
	Filesystem string `json:"filesystem"`
	TotalBytes uint64 `json:"total_bytes"`
}

// NetworkAsset 网卡资产。
type NetworkAsset struct {
	InterfaceName string `json:"interface_name"`
	MACAddress    string `json:"mac_address"`
	IPAddress     string `json:"ip_address"`
}

// Metrics 一轮指标。
type Metrics struct {
	CPUUsage        float64 `json:"cpu_usage"`
	MemoryUsage     float64 `json:"memory_usage"`
	MemoryUsedBytes uint64  `json:"memory_used_bytes"`
	DiskUsage       float64 `json:"disk_usage"`
	NetworkInBytes  uint64  `json:"network_in_bytes"`
	NetworkOutBytes uint64  `json:"network_out_bytes"`
	Load1m          float64 `json:"load_1m"`
	Load5m          float64 `json:"load_5m"`
	Load15m         float64 `json:"load_15m"`
	TCPConnections  int     `json:"tcp_connections"`
	UptimeSeconds   uint64  `json:"uptime_seconds"`
}

// SystemInfo 注册所需的系统信息。
type SystemInfo struct {
	Hostname         string `json:"hostname"`
	OSName           string `json:"os_name"`
	OSVersion        string `json:"os_version"`
	KernelVersion    string `json:"kernel_version"`
	Architecture     string `json:"architecture"`
	CPUModel         string `json:"cpu_model"`
	CPUCores         int    `json:"cpu_cores"`
	MemoryTotalBytes uint64 `json:"memory_total_bytes"`
	DiskTotalBytes   uint64 `json:"disk_total_bytes"`
}

// round2 保留两位小数，与 Python round(x, 2) 对齐。
func round2(v float64) float64 {
	return float64(int64(v*100+0.5)) / 100
}

// collectCPU 采集 CPU 使用率（采样 500ms）与逻辑核心数。
func collectCPU() (usage float64, cores int) {
	percentages, err := cpu.Percent(500*1000*1000, false)
	if err == nil && len(percentages) > 0 {
		usage = round2(percentages[0])
	}
	cores, err = cpu.Counts(true)
	if err != nil {
		cores = 0
	}
	return usage, cores
}

// cpuModel 从 /proc/cpuinfo 读取 CPU 型号。
func cpuModel() string {
	raw, err := os.ReadFile("/proc/cpuinfo")
	if err != nil {
		return ""
	}
	for _, line := range strings.Split(string(raw), "\n") {
		if strings.HasPrefix(line, "model name") {
			parts := strings.SplitN(line, ":", 2)
			if len(parts) == 2 {
				return strings.TrimSpace(parts[1])
			}
		}
	}
	return ""
}

// CollectMetrics 采集一轮指标。
func CollectMetrics() Metrics {
	cpuUsage, _ := collectCPU()
	diskUsage, _ := disk.Usage("/")
	ioCounters, err := net.IOCounters(false)
	var inBytes, outBytes uint64
	if err == nil && len(ioCounters) > 0 {
		inBytes = ioCounters[0].BytesRecv
		outBytes = ioCounters[0].BytesSent
	}
	avg, _ := load.Avg()
	var l1, l5, l15 float64
	if avg != nil {
		l1, l5, l15 = round2(avg.Load1), round2(avg.Load5), round2(avg.Load15)
	}
	uptime, _ := host.Uptime()
	vm, err := mem.VirtualMemory()
	var memUsage float64
	var memUsed uint64
	if err == nil {
		memUsage = round2(vm.UsedPercent)
		memUsed = vm.Used
	}
	m := Metrics{
		CPUUsage:        cpuUsage,
		MemoryUsage:     memUsage,
		MemoryUsedBytes: memUsed,
		DiskUsage:       round2(diskUsage.UsedPercent),
		NetworkInBytes:  inBytes,
		NetworkOutBytes: outBytes,
		Load1m:          l1,
		Load5m:          l5,
		Load15m:         l15,
		TCPConnections:  readTCPConnections(),
		UptimeSeconds:   uptime,
	}
	return m
}

// readTCPConnections 统计 /proc/net/tcp 与 tcp6 的连接行数（去掉表头）。
func readTCPConnections() int {
	total := 0
	for _, path := range []string{"/proc/net/tcp", "/proc/net/tcp6"} {
		raw, err := os.ReadFile(path)
		if err != nil {
			continue
		}
		lines := strings.Split(strings.TrimRight(string(raw), "\n"), "\n")
		if len(lines) > 0 {
			total += len(lines) - 1
		}
	}
	if total < 0 {
		return 0
	}
	return total
}

// CollectDiskUsagePercent 采集根分区使用率。
func CollectDiskUsagePercent() float64 {
	usage, err := disk.Usage("/")
	if err != nil {
		return 0
	}
	return round2(usage.UsedPercent)
}

// CollectDiskAssets 采集磁盘资产（仅本机物理分区）。
func CollectDiskAssets() []DiskAsset {
	assets := make([]DiskAsset, 0)
	partitions, err := disk.Partitions(false)
	if err != nil {
		return assets
	}
	for _, p := range partitions {
		usage, err := disk.Usage(p.Mountpoint)
		if err != nil {
			continue
		}
		assets = append(assets, DiskAsset{
			DeviceName: p.Device,
			MountPoint: p.Mountpoint,
			Filesystem: p.Fstype,
			TotalBytes: usage.Total,
		})
	}
	return assets
}

// CollectNetworkCounts 采集全网络累计发送/接收字节数。
func CollectNetworkCounts() (inBytes, outBytes uint64) {
	counters, err := net.IOCounters(false)
	if err != nil || len(counters) == 0 {
		return 0, 0
	}
	return counters[0].BytesRecv, counters[0].BytesSent
}

// CollectNetworkAssets 采集网卡资产（排除回环）。
func CollectNetworkAssets() []NetworkAsset {
	assets := make([]NetworkAsset, 0)
	interfaces, err := net.Interfaces()
	if err != nil {
		return assets
	}
	for _, iface := range interfaces {
		if iface.Name == "lo" {
			continue
		}
		var ip string
		for _, addr := range iface.Addrs {
			if addr.Addr == "" {
				continue
			}
			ip = strings.Split(addr.Addr, "/")[0]
			break
		}
		assets = append(assets, NetworkAsset{
			InterfaceName: iface.Name,
			MACAddress:    iface.HardwareAddr,
			IPAddress:     ip,
		})
	}
	return assets
}

// CollectSystemInfo 采集注册所需系统信息。
func CollectSystemInfo() SystemInfo {
	hostname, _ := os.Hostname()
	info, err := host.Info()
	var osName, osVersion, kernel, arch string
	if err == nil {
		osName = info.Platform
		osVersion = info.PlatformVersion
		kernel = info.KernelVersion
		arch = info.KernelArch
	}
	_, cores := collectCPU()
	vm, err := mem.VirtualMemory()
	var memTotal uint64
	if err == nil {
		memTotal = vm.Total
	}
	var diskTotal uint64
	for _, d := range CollectDiskAssets() {
		diskTotal += d.TotalBytes
	}
	return SystemInfo{
		Hostname:         hostname,
		OSName:           osName,
		OSVersion:        osVersion,
		KernelVersion:    kernel,
		Architecture:     arch,
		CPUModel:         cpuModel(),
		CPUCores:         cores,
		MemoryTotalBytes: memTotal,
		DiskTotalBytes:   diskTotal,
	}
}

// CollectAssets 采集磁盘与网卡资产。
func CollectAssets() (disks []DiskAsset, networks []NetworkAsset) {
	return CollectDiskAssets(), CollectNetworkAssets()
}
