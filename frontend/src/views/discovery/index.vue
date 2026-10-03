<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import { getDiscoveryConfigApi, scanNetworkApi } from '../../api/discovery'

const router = useRouter()
const config = ref({ enabled: false, allowed_cidrs: [], max_hosts: 256, ssh_port: 22 })
const cidr = ref('')
const port = ref(null)
const loading = ref(false)
const hosts = ref([])
const scanned = ref(false)

async function loadConfig() {
  try {
    config.value = await getDiscoveryConfigApi()
    if (!cidr.value && config.value.allowed_cidrs?.length) {
      cidr.value = config.value.allowed_cidrs[0]
    }
  } catch {
    // 错误已由请求拦截器提示
  }
}

async function scan() {
  if (!cidr.value) {
    ElMessage.warning('请输入待扫描网段')
    return
  }
  loading.value = true
  try {
    const res = await scanNetworkApi({ cidr: cidr.value, port: port.value || undefined })
    hosts.value = res.hosts
    scanned.value = true
    ElMessage.success(`发现 ${res.count} 台开放主机`)
  } catch {
    // 错误已由请求拦截器提示
  } finally {
    loading.value = false
  }
}

function goOnboard() {
  router.push('/servers')
}

onMounted(loadConfig)
</script>

<template>
  <div class="p-4 sm:p-6">
    <div class="mb-4">
      <h2 class="text-lg font-semibold">服务器发现</h2>
      <p class="text-sm text-[var(--el-text-color-secondary)]">
        在授权白名单网段内做只读端口 / SSH banner 探测，不持有凭据、不远程安装；接入请使用服务器管理中的 Agent 向导。
      </p>
    </div>

    <el-alert
      v-if="!config.enabled"
      type="warning"
      :closable="false"
      class="mb-4"
      title="发现功能未启用"
      description="请在部署配置中设置 DISCOVERY_ENABLED=true 并配置 DISCOVERY_ALLOWED_CIDRS 白名单。"
    />

    <el-card shadow="never" class="mb-4">
      <div class="flex flex-wrap items-end gap-3">
        <el-input
          v-model="cidr"
          placeholder="待扫描网段，如 10.0.0.0/24"
          :disabled="!config.enabled"
          style="max-width: 260px"
        />
        <el-input-number
          v-model="port"
          :min="1"
          :max="65535"
          :placeholder="`端口（默认 ${config.ssh_port}）`"
          :disabled="!config.enabled"
        />
        <el-button
          type="primary"
          :icon="Search"
          :loading="loading"
          :disabled="!config.enabled"
          @click="scan"
        >
          扫描
        </el-button>
        <span class="text-xs text-[var(--el-text-color-secondary)]">
          白名单：{{ config.allowed_cidrs?.join(', ') || '未配置' }}（上限 {{ config.max_hosts }} 台）
        </span>
      </div>
    </el-card>

    <el-card shadow="never">
      <el-table v-if="hosts.length" :data="hosts" border>
        <el-table-column prop="ip" label="IP" min-width="160" />
        <el-table-column prop="port" label="端口" width="90" />
        <el-table-column prop="banner" label="Banner" min-width="220" show-overflow-tooltip />
        <el-table-column label="操作" width="110">
          <template #default>
            <el-button link type="primary" @click="goOnboard">去接入</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-else-if="scanned" description="未发现开放主机" />
      <el-empty v-else description="输入网段后点击扫描" />
    </el-card>
  </div>
</template>
