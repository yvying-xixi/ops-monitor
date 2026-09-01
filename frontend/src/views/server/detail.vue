<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { getLatestMetricApi, getServerAssetsApi, getSummaryMetricApi } from '../../api/monitor'
import MetricChart from '../../components/MetricChart.vue'
import { AGENT_STATUS_MAP, TIME_RANGES } from '../../config'
import { formatBytes, formatTime, formatUptime } from '../../utils/format'

const route = useRoute()
const serverId = Number(route.params.id)

const latest = ref(null)
const assets = ref({ disks: [], networks: [] })
const timeRange = ref('1h')
const summary = ref(null)
let timer = null

const statusLabel = computed(() => AGENT_STATUS_MAP[latest.value?.server?.agent_status] || AGENT_STATUS_MAP.UNKNOWN)
const serverInfo = computed(() => latest.value?.server || {})

async function loadLatest() {
  latest.value = await getLatestMetricApi(serverId)
}

async function loadAssets() {
  assets.value = await getServerAssetsApi(serverId)
}

async function loadSummary() {
  summary.value = await getSummaryMetricApi(serverId, timeRange.value)
}

function metricSeries(field, names) {
  const xAxis = summary.value.points.map((p) => new Date(p.time).toLocaleTimeString('zh-CN', { hour12: false }))
  const series = []
  if (names.avg) series.push({ name: '平均', data: summary.value.points.map((p) => p[field]?.avg ?? null) })
  if (names.max) series.push({ name: '最高', data: summary.value.points.map((p) => p[field]?.max ?? null) })
  if (names.min) series.push({ name: '最低', data: summary.value.points.map((p) => p[field]?.min ?? null) })
  return { xAxis, series }
}

const cpuChart = computed(() => summary.value && metricSeries('cpu_usage', { avg: true, max: true, min: true }))
const memoryChart = computed(() => summary.value && metricSeries('memory_usage', { avg: true, max: true, min: true }))
const diskChart = computed(() => summary.value && metricSeries('disk_usage', { avg: true, max: true, min: true }))
const loadChart = computed(() => {
  if (!summary.value) return null
  return {
    xAxis: summary.value.points.map((p) => new Date(p.time).toLocaleTimeString('zh-CN', { hour12: false })),
    series: [
      { name: '1m', data: summary.value.points.map((p) => p.load_1m?.avg ?? null), color: '#409eff' },
      { name: '5m', data: summary.value.points.map((p) => p.load_5m?.avg ?? null), color: '#67c23a' },
      { name: '15m', data: summary.value.points.map((p) => p.load_15m?.avg ?? null), color: '#e6a23c' },
    ],
  }
})
const networkChart = computed(() => {
  if (!summary.value) return null
  return {
    xAxis: summary.value.points.map((p) => new Date(p.time).toLocaleTimeString('zh-CN', { hour12: false })),
    series: [
      { name: '入站', data: summary.value.points.map((p) => p.network_in_rate ?? 0), color: '#409eff', area: true },
      { name: '出站', data: summary.value.points.map((p) => p.network_out_rate ?? 0), color: '#67c23a', area: true },
    ],
  }
})

function refreshAll() {
  loadLatest()
  loadSummary()
}

onMounted(() => {
  refreshAll()
  loadAssets()
  timer = setInterval(() => loadLatest(), 10000)
})
onUnmounted(() => clearInterval(timer))
</script>

<template>
  <div>
    <el-card shadow="never" class="info-card">
      <template #header>
        <div class="header-row">
          <span>{{ serverInfo.hostname }} ({{ serverInfo.server_code }})</span>
          <el-tag :type="statusLabel.type">{{ statusLabel.label }}</el-tag>
        </div>
      </template>
      <el-descriptions :column="4" border>
        <el-descriptions-item label="IP 地址">{{ serverInfo.ip_address }}</el-descriptions-item>
        <el-descriptions-item label="系统">{{ serverInfo.os_name }} {{ serverInfo.os_version }}</el-descriptions-item>
        <el-descriptions-item label="CPU 核心">{{ serverInfo.cpu_cores }}</el-descriptions-item>
        <el-descriptions-item label="内存总量">{{ formatBytes(serverInfo.memory_total_bytes) }}</el-descriptions-item>
        <el-descriptions-item label="磁盘总量">{{ formatBytes(serverInfo.disk_total_bytes) }}</el-descriptions-item>
        <el-descriptions-item label="Agent 版本">{{ serverInfo.agent_version || '-' }}</el-descriptions-item>
        <el-descriptions-item label="注册时间">{{ formatTime(serverInfo.registered_at) }}</el-descriptions-item>
        <el-descriptions-item label="最后心跳">{{ formatTime(serverInfo.last_heartbeat_at) }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-row :gutter="16" class="row">
      <el-col :span="6">
        <el-card shadow="hover"><div class="realtime"><div class="label">CPU 使用率</div><div class="value">{{ latest?.metric?.cpu_usage ?? '-' }}%</div></div></el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover"><div class="realtime"><div class="label">内存使用率</div><div class="value">{{ latest?.metric?.memory_usage ?? '-' }}%</div></div></el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover"><div class="realtime"><div class="label">磁盘使用率</div><div class="value">{{ latest?.metric?.disk_usage ?? '-' }}%</div></div></el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover"><div class="realtime"><div class="label">TCP 连接数</div><div class="value">{{ latest?.metric?.tcp_connections ?? '-' }}</div></div></el-card>
      </el-col>
    </el-row>
    <el-row :gutter="16" class="row">
      <el-col :span="6">
        <el-card shadow="hover"><div class="realtime"><div class="label">Load(1m)</div><div class="value">{{ latest?.metric?.load_1m ?? '-' }}</div></div></el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover"><div class="realtime"><div class="label">运行时长</div><div class="value small">{{ formatUptime(latest?.metric?.uptime_seconds) }}</div></div></el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover"><div class="realtime"><div class="label">内存使用</div><div class="value small">{{ formatBytes(latest?.metric?.memory_used_bytes) }}</div></div></el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover"><div class="realtime"><div class="label">数据更新时间</div><div class="value small">{{ formatTime(latest?.metric?.collected_at) }}</div></div></el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" class="row">
      <template #header>
        <div class="header-row">
          <span>历史趋势</span>
          <el-radio-group v-model="timeRange" size="small" @change="loadSummary">
            <el-radio-button v-for="r in TIME_RANGES" :key="r.value" :value="r.value">{{ r.label }}</el-radio-button>
          </el-radio-group>
        </div>
      </template>
      <el-row :gutter="16">
        <el-col :span="12"><MetricChart v-if="cpuChart" title="CPU 使用率" :x-axis="cpuChart.xAxis" :series="cpuChart.series" unit="%" y-name="%" /></el-col>
        <el-col :span="12"><MetricChart v-if="memoryChart" title="内存使用率" :x-axis="memoryChart.xAxis" :series="memoryChart.series" unit="%" y-name="%" /></el-col>
      </el-row>
      <el-row :gutter="16" class="row">
        <el-col :span="12"><MetricChart v-if="diskChart" title="磁盘使用率" :x-axis="diskChart.xAxis" :series="diskChart.series" unit="%" y-name="%" /></el-col>
        <el-col :span="12"><MetricChart v-if="networkChart" title="网络流量" :x-axis="networkChart.xAxis" :series="networkChart.series" unit="MB/s" y-name="MB/s" /></el-col>
      </el-row>
      <el-row :gutter="16" class="row">
        <el-col :span="12"><MetricChart v-if="loadChart" title="Load Average" :x-axis="loadChart.xAxis" :series="loadChart.series" /></el-col>
      </el-row>
    </el-card>

    <el-card shadow="never" class="row">
      <template #header>磁盘资产</template>
      <el-table :data="assets.disks">
        <el-table-column prop="device_name" label="设备" min-width="120" />
        <el-table-column prop="mount_point" label="挂载点" min-width="120" />
        <el-table-column prop="filesystem" label="文件系统" width="100" />
        <el-table-column label="总容量" width="120">
          <template #default="{ row }">{{ formatBytes(row.total_bytes) }}</template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card shadow="never" class="row">
      <template #header>网卡资产</template>
      <el-table :data="assets.networks">
        <el-table-column prop="interface_name" label="网卡" min-width="120" />
        <el-table-column prop="mac_address" label="MAC" min-width="140" />
        <el-table-column prop="ip_address" label="IP" min-width="130" />
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.info-card {
  margin-bottom: 16px;
}
.header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.row {
  margin-bottom: 16px;
}
.realtime {
  text-align: center;
}
.realtime .label {
  color: #909399;
  margin-bottom: 8px;
}
.realtime .value {
  font-size: 26px;
  font-weight: 700;
}
.realtime .value.small {
  font-size: 18px;
}
</style>
