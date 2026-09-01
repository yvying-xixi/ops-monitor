<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
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
  tokenVisible.value = true
  tokenLoading.value = true
  try {
    tokenData.value = await generateAgentTokenApi(server.id)
  } finally {
    tokenLoading.value = false
  }
}

async function copyToken() {
  await navigator.clipboard.writeText(tokenData.value.token)
  ElMessage.success('已复制到剪贴板')
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
      <el-table-column label="编码" prop="server_code" min-width="100" />
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
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="goDetail(row.id)">详情</el-button>
          <el-button link type="warning" @click="openToken(row)">凭证</el-button>
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
          <el-input v-model="createForm.server_code" placeholder="如 web-01" />
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

    <!-- 生成凭证 -->
    <el-dialog v-model="tokenVisible" title="Agent 注册凭证" width="520px">
      <el-alert type="warning" :closable="false" show-icon title="凭证明文仅展示一次，请立即保存；丢失需重新生成。" class="alert" />
      <el-skeleton :loading="tokenLoading" animated>
        <div v-if="tokenData" class="token-box">
          <div class="token-line"><span>服务器：</span>{{ currentServer?.hostname }} ({{ currentServer?.server_code }})</div>
          <div class="token-line"><span>Token 明文：</span></div>
          <el-input :model-value="tokenData.token" readonly>
            <template #append>
              <el-button @click="copyToken">复制</el-button>
            </template>
          </el-input>
          <div class="token-line"><span>Token 前缀：</span>{{ tokenData.token_prefix }}</div>
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
.token-line {
  margin: 8px 0;
}
</style>
