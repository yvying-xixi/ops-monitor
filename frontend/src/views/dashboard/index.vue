<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getDashboardOverviewApi } from '../../api/monitor'
import { AGENT_STATUS_MAP } from '../../config'
import { formatTime } from '../../utils/format'

const router = useRouter()
const loading = ref(false)
const overview = ref({ server_stats: {}, avg_usage: {}, servers: [] })
let timer = null

async function loadData() {
  loading.value = true
  try {
    overview.value = await getDashboardOverviewApi()
  } finally {
    loading.value = false
  }
}

function statusLabel(status) {
  return AGENT_STATUS_MAP[status] || AGENT_STATUS_MAP.UNKNOWN
}

function usagePercent(value) {
  return value === null || value === undefined ? 0 : Number(value).toFixed(1)
}

function usageType(value) {
  if (value === null || value === undefined) return 'info'
  if (value >= 90) return 'danger'
  if (value >= 75) return 'warning'
  return 'success'
}

function goDetail(id) {
  router.push(`/servers/${id}`)
}

onMounted(() => {
  loadData()
  timer = setInterval(loadData, 10000)
})
onUnmounted(() => clearInterval(timer))
</script>

<template>
  <div class="dashboard">
    <el-row :gutter="16">
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat">
            <div class="stat-label">服务器总数</div>
            <div class="stat-value">{{ overview.server_stats.total || 0 }}</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat">
            <div class="stat-label">在线</div>
            <div class="stat-value" style="color: #67c23a">{{ overview.server_stats.ONLINE || 0 }}</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat">
            <div class="stat-label">警告</div>
            <div class="stat-value" style="color: #e6a23c">{{ overview.server_stats.WARNING || 0 }}</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat">
            <div class="stat-label">离线</div>
            <div class="stat-value" style="color: #f56c6c">{{ overview.server_stats.OFFLINE || 0 }}</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="row">
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat">
            <div class="stat-label">CPU 平均使用率</div>
            <el-progress :percentage="Number(usagePercent(overview.avg_usage.cpu))" :status="usageType(overview.avg_usage.cpu)" :stroke-width="14" />
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat">
            <div class="stat-label">内存平均使用率</div>
            <el-progress :percentage="Number(usagePercent(overview.avg_usage.memory))" :status="usageType(overview.avg_usage.memory)" :stroke-width="14" />
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat">
            <div class="stat-label">磁盘平均使用率</div>
            <el-progress :percentage="Number(usagePercent(overview.avg_usage.disk))" :status="usageType(overview.avg_usage.disk)" :stroke-width="14" />
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="alert-card" @click="router.push('/alerts')">
          <div class="stat">
            <div class="stat-label">实时告警</div>
            <div class="stat-value" :style="{ color: overview.active_alerts > 0 ? '#f56c6c' : '#67c23a' }">
              {{ overview.active_alerts || 0 }}
            </div>
            <div class="stat-tip">点击进入告警中心</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="hover" class="row">
      <template #header>服务器列表</template>
      <el-table :data="overview.servers" v-loading="loading">
        <el-table-column label="主机名" prop="server.hostname" min-width="120" />
        <el-table-column label="编码" prop="server.server_code" min-width="100" />
        <el-table-column label="IP" prop="server.ip_address" min-width="130" />
        <el-table-column label="系统" min-width="120">
          <template #default="{ row }">{{ row.server.os_name || '-' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="statusLabel(row.server.agent_status).type">{{ statusLabel(row.server.agent_status).label }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="CPU" width="90">
          <template #default="{ row }">{{ row.latest ? `${usagePercent(row.latest.cpu_usage)}%` : '-' }}</template>
        </el-table-column>
        <el-table-column label="内存" width="90">
          <template #default="{ row }">{{ row.latest ? `${usagePercent(row.latest.memory_usage)}%` : '-' }}</template>
        </el-table-column>
        <el-table-column label="磁盘" width="90">
          <template #default="{ row }">{{ row.latest ? `${usagePercent(row.latest.disk_usage)}%` : '-' }}</template>
        </el-table-column>
        <el-table-column label="最后心跳" min-width="150">
          <template #default="{ row }">{{ formatTime(row.server.last_heartbeat_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="90" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="goDetail(row.server.id)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.row {
  margin-top: 16px;
}
.alert-card {
  cursor: pointer;
}
.stat-label {
  color: #909399;
  margin-bottom: 12px;
}
.stat-value {
  font-size: 28px;
  font-weight: 700;
}
.stat-tip {
  color: #c0c4cc;
  font-size: 12px;
  margin-top: 4px;
}
</style>
