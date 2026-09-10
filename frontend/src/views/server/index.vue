<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { createServerApi, generateAgentTokenApi, listServersApi } from '../../api/server'
import { AGENT_STATUS_MAP } from '../../config'
import { formatTime } from '../../utils/format'

const router = useRouter()
const loading = ref(false)
const rows = ref([])
const total = ref(0)
const query = reactive({ page: 1, page_size: 10, agent_status: '' })

const createVisible = ref(false)
const createForm = reactive({ server_code: '', hostname: '', ip_address: '', ssh_port: 22, remark: '' })
const createLoading = ref(false)

const tokenVisible = ref(false)
const tokenLoading = ref(false)
const tokenData = ref(null)
const currentServer = ref(null)

// 接入向导表单：后端地址与服务白名单可编辑
const agentForm = reactive({ serverUrl: window.location.origin, services: 'nginx,docker,ssh' })

function statusLabel(status) {
  return AGENT_STATUS_MAP[status] || AGENT_STATUS_MAP.UNKNOWN
}

async function loadData() {
  loading.value = true
  try {
    const data = await listServersApi(query)
    rows.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

function goDetail(id) {
  router.push(`/servers/${id}`)
}

async function handleCreate() {
  createLoading.value = true
  try {
    await createServerApi(createForm)
    ElMessage.success('创建成功')
    createVisible.value = false
    Object.assign(createForm, { server_code: '', hostname: '', ip_address: '', ssh_port: 22, remark: '' })
    await loadData()
  } finally {
    createLoading.value = false
  }
}

async function openToken(server) {
  currentServer.value = server
  tokenData.value = null
  agentForm.serverUrl = window.location.origin
  agentForm.services = 'nginx,docker,ssh'
  tokenVisible.value = true
  tokenLoading.value = true
  try {
    tokenData.value = await generateAgentTokenApi(server.id)
  } finally {
    tokenLoading.value = false
  }
}

async function copyText(text, label = '已复制') {
  if (!text) return
  await navigator.clipboard.writeText(text)
  ElMessage.success(label)
}

function copyToken() {
  copyText(tokenData.value?.token, 'Token 已复制')
}

function copyServerCode() {
  copyText(currentServer.value?.server_code, '服务器编码已复制')
}

function copyConfig() {
  copyText(configYaml.value, 'config.yaml 已复制')
}

const serviceList = computed(() =>
  agentForm.services.split(',').map((s) => s.trim()).filter(Boolean),
)

const configYaml = computed(() => {
  const lines = serviceList.value.map((s) => `    - "${s}"`).join('\n')
  return [
    'server:',
    `  url: "${agentForm.serverUrl}"`,
    `  token: "${tokenData.value?.token || ''}"`,
    `  server_code: "${currentServer.value?.server_code || ''}"`,
    '',
    'collect:',
    '  heartbeat_interval: 30',
    '  metrics_interval: 10',
    '  assets_interval: 60',
    '  task_poll_interval: 5',
    '  retry_max_seconds: 60',
    '  connect_timeout: 5',
    '  request_timeout: 10',
    '  services:',
    lines || '    - "nginx"',
    '',
    'log:',
    '  level: "INFO"',
    '',
  ].join('\n')
})

const deployCommands = computed(() => ({
  foreground: [
    '# 前台运行（调试）',
    'cd /path/to/ops-monitor',
    './agent/.venv/bin/python -m agent.main',
  ].join('\n'),
  systemd: [
    '# 将上方 config.yaml 保存到目标机后，一键安装为 systemd 服务',
    'sudo ./agent/install.sh',
  ].join('\n'),
  docker: [
    '# 容器化运行（宿主机指标采集；容器内服务控制默认关闭）',
    'docker run -d --name ops-agent --restart unless-stopped \\',
    '  --pid=host --network=host \\',
    '  -v /proc:/host/proc:ro -v /sys:/host/sys:ro \\',
    '  -v $(pwd)/config.yaml:/app/agent/config/config.yaml:ro \\',
    '  ops-monitor-agent:latest',
  ].join('\n'),
}))

function downloadConfig() {
  const blob = new Blob([configYaml.value], { type: 'text/yaml;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `config-${currentServer.value?.server_code || 'agent'}.yaml`
  a.click()
  URL.revokeObjectURL(url)
}

onMounted(loadData)
</script>

<template>
  <el-card shadow="never">
    <div class="toolbar">
      <el-form inline @submit.prevent>
        <el-form-item label="状态">
          <el-select v-model="query.agent_status" clearable placeholder="全部" style="width: 120px" @change="loadData">
            <el-option label="在线" value="ONLINE" />
            <el-option label="警告" value="WARNING" />
            <el-option label="离线" value="OFFLINE" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadData">查询</el-button>
        </el-form-item>
      </el-form>
      <el-button type="primary" @click="createVisible = true">新增服务器</el-button>
    </div>

    <el-table :data="rows" v-loading="loading">
      <el-table-column label="编码" prop="server_code" min-width="120">
        <template #default="{ row }">
          <span class="code-cell">
            {{ row.server_code }}
            <el-button link type="primary" size="small" @click="copyText(row.server_code, '服务器编码已复制')">复制</el-button>
          </span>
        </template>
      </el-table-column>
      <el-table-column label="主机名" prop="hostname" min-width="120" />
      <el-table-column label="IP" prop="ip_address" min-width="130" />
      <el-table-column label="SSH 端口" prop="ssh_port" width="90" />
      <el-table-column label="系统" min-width="110">
        <template #default="{ row }">{{ row.os_name || '-' }}</template>
      </el-table-column>
      <el-table-column label="Agent" width="80">
        <template #default="{ row }">{{ row.agent_version || '-' }}</template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="statusLabel(row.agent_status).type">{{ statusLabel(row.agent_status).label }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="最后心跳" min-width="150">
        <template #default="{ row }">{{ formatTime(row.last_heartbeat_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="190" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="goDetail(row.id)">详情</el-button>
          <el-button link type="warning" @click="openToken(row)">接入</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      class="pagination"
      layout="total, prev, pager, next, sizes"
      :total="total"
      v-model:current-page="query.page"
      v-model:page-size="query.page_size"
      :page-sizes="[10, 20, 50]"
      @current-change="loadData"
      @size-change="loadData"
    />

    <!-- 新增服务器 -->
    <el-dialog v-model="createVisible" title="新增服务器" width="480px">
      <el-form :model="createForm" label-width="90px">
        <el-form-item label="服务器编码" required>
          <el-input v-model="createForm.server_code" placeholder="如 web-01（Agent 注册匹配键）" />
        </el-form-item>
        <el-form-item label="主机名" required>
          <el-input v-model="createForm.hostname" />
        </el-form-item>
        <el-form-item label="IP 地址" required>
          <el-input v-model="createForm.ip_address" />
        </el-form-item>
        <el-form-item label="SSH 端口">
          <el-input-number v-model="createForm.ssh_port" :min="1" :max="65535" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="createForm.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="createLoading" @click="handleCreate">确定</el-button>
      </template>
    </el-dialog>

    <!-- Agent 接入向导 -->
    <el-dialog v-model="tokenVisible" title="Agent 接入向导" width="720px">
      <el-alert
        type="warning"
        :closable="false"
        show-icon
        title="Token 明文仅展示一次，请立即复制或下载配置；丢失需重新生成。"
        class="alert"
      />
      <el-skeleton :loading="tokenLoading" animated>
        <div v-if="tokenData" class="wizard">
          <el-steps :active="4" simple>
            <el-step title="生成凭证" />
            <el-step title="配置 Agent" />
            <el-step title="部署运行" />
            <el-step title="验证上线" />
          </el-steps>

          <div class="section">
            <div class="section-title">1. 凭证信息</div>
            <div class="field">
              <span class="field-label">服务器编码（server_code，注册匹配键）</span>
              <el-input :model-value="currentServer?.server_code" readonly>
                <template #append><el-button @click="copyServerCode">复制</el-button></template>
              </el-input>
            </div>
            <div class="field">
              <span class="field-label">Token 明文</span>
              <el-input :model-value="tokenData.token" readonly>
                <template #append><el-button @click="copyToken">复制</el-button></template>
              </el-input>
            </div>
            <div class="field">
              <span class="field-label">主机名</span>
              <el-input :model-value="currentServer?.hostname" readonly />
            </div>
          </div>

          <div class="section">
            <div class="section-title">2. Agent 配置（可编辑）</div>
            <div class="field">
              <span class="field-label">服务端地址（Agent 所在网络可访问的地址）</span>
              <el-input v-model="agentForm.serverUrl" placeholder="http://<平台IP>:8000 或 http://<平台IP>" />
            </div>
            <div class="field">
              <span class="field-label">服务白名单（英文逗号分隔，用于状态监控与受控操作）</span>
              <el-input v-model="agentForm.services" placeholder="nginx,docker,ssh" />
            </div>
          </div>

          <div class="section">
            <div class="section-title">
              3. config.yaml
              <el-button link type="primary" @click="copyConfig">复制</el-button>
              <el-button link type="primary" @click="downloadConfig">下载</el-button>
            </div>
            <pre class="config-pre">{{ configYaml }}</pre>
          </div>

          <div class="section">
            <div class="section-title">4. 部署命令</div>
            <div class="field">
              <span class="field-label">前台运行
                <el-button link type="primary" size="small" @click="copyText(deployCommands.foreground, '命令已复制')">复制</el-button>
              </span>
              <pre class="cmd-pre">{{ deployCommands.foreground }}</pre>
            </div>
            <div class="field">
              <span class="field-label">systemd 安装（推荐）
                <el-button link type="primary" size="small" @click="copyText(deployCommands.systemd, '命令已复制')">复制</el-button>
              </span>
              <pre class="cmd-pre">{{ deployCommands.systemd }}</pre>
            </div>
            <div class="field">
              <span class="field-label">Docker 运行
                <el-button link type="primary" size="small" @click="copyText(deployCommands.docker, '命令已复制')">复制</el-button>
              </span>
              <pre class="cmd-pre">{{ deployCommands.docker }}</pre>
            </div>
          </div>
        </div>
      </el-skeleton>
    </el-dialog>
  </el-card>
</template>

<style scoped>
.toolbar {
  display: flex;
  justify-content: space-between;
  margin-bottom: 12px;
}
.pagination {
  margin-top: 12px;
  justify-content: flex-end;
}
.alert {
  margin-bottom: 12px;
}
.code-cell {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.wizard {
  max-height: 66vh;
  overflow: auto;
  padding-right: 4px;
}
.section {
  margin-top: 16px;
}
.section-title {
  font-weight: 600;
  margin-bottom: 8px;
}
.field {
  margin-bottom: 10px;
}
.field-label {
  display: block;
  color: #606266;
  font-size: 13px;
  margin-bottom: 4px;
}
.config-pre,
.cmd-pre {
  margin: 0;
  background: #0f172a;
  color: #d1e3ff;
  font-size: 12px;
  padding: 10px;
  border-radius: 4px;
  max-height: 220px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
