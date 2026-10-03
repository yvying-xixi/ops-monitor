package collector

import "testing"

func TestCollectMetricsFields(t *testing.T) {
	m := CollectMetrics()
	if m.CPUUsage < 0 || m.CPUUsage > 100 {
		t.Errorf("cpu_usage 超范围: %v", m.CPUUsage)
	}
	if m.MemoryUsage < 0 || m.MemoryUsage > 100 {
		t.Errorf("memory_usage 超范围: %v", m.MemoryUsage)
	}
	if m.DiskUsage < 0 || m.DiskUsage > 100 {
		t.Errorf("disk_usage 超范围: %v", m.DiskUsage)
	}
	if m.Load1m < 0 || m.Load5m < 0 || m.Load15m < 0 {
		t.Errorf("load 不应为负: %v %v %v", m.Load1m, m.Load5m, m.Load15m)
	}
	if m.TCPConnections < 0 {
		t.Errorf("tcp_connections 不应为负: %d", m.TCPConnections)
	}
}

func TestCollectDiskAssets(t *testing.T) {
	assets := CollectDiskAssets()
	if len(assets) == 0 {
		t.Fatal("应至少采集到一个磁盘资产")
	}
	if assets[0].DeviceName == "" {
		t.Errorf("device_name 为空: %+v", assets[0])
	}
	if assets[0].MountPoint == "" {
		t.Errorf("mount_point 为空: %+v", assets[0])
	}
}

func TestCollectNetworkAssets(t *testing.T) {
	assets := CollectNetworkAssets()
	for _, a := range assets {
		if a.InterfaceName == "" {
			t.Errorf("interface_name 为空: %+v", a)
		}
		if a.InterfaceName == "lo" {
			t.Errorf("不应包含回环接口: %+v", a)
		}
	}
}

func TestCollectSystemInfo(t *testing.T) {
	info := CollectSystemInfo()
	if info.Hostname == "" {
		t.Error("hostname 为空")
	}
	if info.CPUCores <= 0 {
		t.Errorf("cpu_cores = %d, want > 0", info.CPUCores)
	}
	if info.MemoryTotalBytes == 0 {
		t.Error("memory_total_bytes 为 0")
	}
}

func TestCollectAssetsAggregate(t *testing.T) {
	disks, networks := CollectAssets()
	if disks == nil || networks == nil {
		t.Fatal("CollectAssets 不应返回 nil")
	}
}

func TestReadTCPConnectionsNonNegative(t *testing.T) {
	if got := readTCPConnections(); got < 0 {
		t.Errorf("tcp_connections = %d, want >= 0", got)
	}
}
