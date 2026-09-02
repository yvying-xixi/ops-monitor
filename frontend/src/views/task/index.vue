<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createTaskApi, listTasksApi, cancelTaskApi, confirmTaskApi, getTaskApi } from '../../api/task'
import { listServersApi } from '../../api/server'
import { TASK_STATUS_MAP } from '../../config'
import { formatTime } from '../../utils/format'

const loading = ref(false)
const rows = ref([])
const total = ref(0)
const query = reactive({ page: 1, page_size: 10, status: '' })

const createVisible = ref(false)
const createForm = reactive({
  task_name: '',
  task_type: 'SERVICE_CHECK',
  action: 'STATUS',
  service_name: '',
  server_ids: [],
  schedule_type: 'ONCE',
  cron_expression: '',
})
const servers = ref([])
const createLoading = ref(false)

const detailVisible = ref(false)
const detail = ref(null)
const detailLoading = ref(false)

const actionOptions = { SERVICE_CHECK: ['STATUS'], SERVICE_ACTION: ['START', 'STOP', 'RESTART'], SERVICE_LOG: ['LOGS'] }

function statusOf(s) {
  return TASK_STATUS_MAP[s] || { type: 'info', label: s }
}

async function loadData() {
  loading.value = true
  try {
    const data = await listTasksApi(query)
    rows.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

async function openCreate() {
  Object.assign(createForm, {
    task_name: '', task_type: 'SERVICE_CHECK', action: 'STATUS',
    service_name: '', server_ids: [], schedule_type: 'ONCE', cron_expression: '',
  })
  createVisible.value = true
  const data = await listServersApi({ page: 1, page_size: 100 })
  servers.value = data.items
}

function onTypeChange() {
  createForm.action = actionOptions[createForm.task_type][0]
}

async function handleCreate() {
  if (!createForm.task_name || !createForm.server_ids.length) {
    ElMessage.warning('请填写任务名称并选择服务器')
    return
  }
  if (createForm.task_type !== 'SERVICE_CHECK' && !createForm.service_name) {
    ElMessage.warning('请填写服务名称')
    return
  }
  createLoading.value = true
  try {
    const payload = { ...createForm }
    if (payload.task_type === 'SERVICE_CHECK') payload.action = 'STATUS'
    if (payload.schedule_type !== 'CRON') delete payload.cron_expression
    await createTaskApi(payload)
    ElMessage.success('任务已创建')
    createVisible.value = false
    await loadData()
  } finally {
    createLoading.value = false
  }
}

async function openDetail(row) {
  detailLoading.value = true
  detailVisible.value = true
  try {
    detail.value = await getTaskApi(row.id)
  } finally {
    detailLoading.value = false
  }
}

async function handleConfirm(row) {
  await confirmTaskApi(row.id)
  ElMessage.success('已确认')
  await loadData()
}

async function handleCancel(row) {
  await ElMessageBox.confirm(`确定取消任务「${row.task_name}」吗？`, '提示', { type: 'warning' })
  await cancelTaskApi(row.id)
  ElMessage.success('已取消')
  await loadData()
}

onMounted(loadData)
</script>

<template>
  <el-card shadow="never">
    <div class="toolbar">
      <el-form inline @submit.prevent>
        <el-form-item label="状态">
          <el-select v-model="query.status" clearable placeholder="全部" style="width: 130px" @change="loadData">
            <el-option v-for="(v, k) in TASK_STATUS_MAP" :key="k" :label="v.label" :value="k" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadData">查询</el-button>
        </el-form-item>
      </el-form>
      <el-button type="primary" @click="openCreate">新建任务</el-button>
    </div>

    <el-table :data="rows" v-loading="loading">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="task_name" label="任务名称" min-width="150" />
      <el-table-column label="类型" width="100">
        <template #default="{ row }">{{ row.task_type === 'SERVICE_CHECK' ? '服务检查' : row.task_type === 'SERVICE_ACTION' ? '服务操作' : '服务日志' }}</template>
      </el-table-column>
      <el-table-column label="操作 / 服务" min-width="140">
        <template #default="{ row }">{{ row.action || '-' }} {{ row.service_name ? '/ ' + row.service_name : '' }}</template>
      </el-table-column>
      <el-table-column label="调度" width="90">
        <template #default="{ row }">{{ row.schedule_type === 'CRON' ? '定时' : '即时' }}</template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusOf(row.status).type" size="small">{{ statusOf(row.status).label }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="创建时间" min-width="150">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)">详情</el-button>
          <el-button v-if="row.status === 'CREATED'" link type="warning" @click="handleConfirm(row)">确认</el-button>
          <el-button v-if="['CREATED', 'PENDING', 'RUNNING'].includes(row.status)" link type="danger" @click="handleCancel(row)">取消</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      class="pagination"
      layout="total, prev, pager, next"
      :total="total"
      v-model:current-page="query.page"
      v-model:page-size="query.page_size"
      @current-change="loadData"
    />

    <!-- 新建任务 -->
    <el-dialog v-model="createVisible" title="新建任务" width="520px">
      <el-form :model="createForm" label-width="90px">
        <el-form-item label="任务名称" required>
          <el-input v-model="createForm.task_name" />
        </el-form-item>
        <el-form-item label="任务类型">
          <el-radio-group v-model="createForm.task_type" @change="onTypeChange">
            <el-radio value="SERVICE_CHECK">服务检查</el-radio>
            <el-radio value="SERVICE_ACTION">服务操作</el-radio>
            <el-radio value="SERVICE_LOG">服务日志</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="操作">
          <el-select v-model="createForm.action" style="width: 200px">
            <el-option v-for="a in actionOptions[createForm.task_type]" :key="a" :label="a" :value="a" />
          </el-select>
        </el-form-item>
        <el-form-item label="服务名称">
          <el-input v-model="createForm.service_name" placeholder="如 nginx / docker / ssh" :disabled="createForm.task_type === 'SERVICE_CHECK'" />
        </el-form-item>
        <el-form-item label="目标服务器" required>
          <el-select v-model="createForm.server_ids" multiple style="width: 100%" placeholder="支持多选批量">
            <el-option v-for="s in servers" :key="s.id" :label="`${s.hostname} (${s.ip_address})`" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="调度">
          <el-radio-group v-model="createForm.schedule_type">
            <el-radio value="ONCE">即时执行</el-radio>
            <el-radio value="CRON">定时执行</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="createForm.schedule_type === 'CRON'" label="Cron">
          <el-input v-model="createForm.cron_expression" placeholder="5 字段，如 */5 * * * *" />
        </el-form-item>
      </el-form>
      <el-alert v-if="['START', 'STOP', 'RESTART'].includes(createForm.action)" type="warning" :closable="false" title="该操作为高风险操作，创建后需二次确认。" />
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="createLoading" @click="handleCreate">提交</el-button>
      </template>
    </el-dialog>

    <!-- 任务详情 -->
    <el-dialog v-model="detailVisible" title="任务详情" width="720px" v-loading="detailLoading">
      <template v-if="detail">
        <el-descriptions :column="3" border>
          <el-descriptions-item label="任务名称">{{ detail.task.task_name }}</el-descriptions-item>
          <el-descriptions-item label="类型">{{ detail.task.task_type }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ statusOf(detail.task.status).label }}</el-descriptions-item>
          <el-descriptions-item label="操作">{{ detail.task.action }}</el-descriptions-item>
          <el-descriptions-item label="服务">{{ detail.task.service_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="调度">{{ detail.task.schedule_type }}</el-descriptions-item>
        </el-descriptions>

        <el-table :data="detail.executions" class="exec-table" border>
          <el-table-column label="服务器" min-width="120">
            <template #default="{ row }">{{ row.server_hostname || row.server_id }}</template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="statusOf(row.status).type" size="small">{{ statusOf(row.status).label }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="exit_code" label="退出码" width="70" />
          <el-table-column label="耗时" width="90">
            <template #default="{ row }">{{ row.duration_ms != null ? row.duration_ms + 'ms' : '-' }}</template>
          </el-table-column>
          <el-table-column label="结果/日志" min-width="200">
            <template #default="{ row }">
              <div v-if="row.result_text" class="log-box">{{ row.result_text }}</div>
              <div v-if="row.error_message" class="log-box error">{{ row.error_message }}</div>
              <pre v-if="row.logs && row.logs.length" class="log-pre">{{ row.logs.join('\n') }}</pre>
            </template>
          </el-table-column>
        </el-table>
      </template>
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
.exec-table {
  margin-top: 12px;
}
.log-box {
  font-size: 12px;
  color: #303133;
  word-break: break-all;
}
.log-box.error {
  color: #f56c6c;
}
.log-pre {
  margin: 4px 0;
  background: #0f172a;
  color: #d1e3ff;
  font-size: 12px;
  padding: 8px;
  border-radius: 4px;
  max-height: 180px;
  overflow: auto;
}
</style>
