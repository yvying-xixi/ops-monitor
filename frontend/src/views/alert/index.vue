<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useUserStore } from '../../store/user'
import {
  ackAlertApi,
  createRuleApi,
  deleteRuleApi,
  getAlertApi,
  listAlertsApi,
  listRulesApi,
  resolveAlertApi,
  updateRuleApi,
} from '../../api/alert'
import { ALERT_METRIC_TYPES, ALERT_OPERATORS, ALERT_SEVERITY_MAP, ALERT_STATUS_MAP } from '../../config'
import { formatTime } from '../../utils/format'

const userStore = useUserStore()
const canOperate = () => userStore.hasRole('SYSTEM_ADMIN', 'OPS_ENGINEER')

// ---------- 事件列表 ----------
const activeTab = ref('events')
const loading = ref(false)
const events = ref([])
const total = ref(0)
const query = reactive({ page: 1, page_size: 10, severity: '', status: '', active: null })

const detailVisible = ref(false)
const detail = ref(null)

function severityOf(sev) {
  return ALERT_SEVERITY_MAP[sev] || { type: 'info', label: sev }
}
function statusOf(status) {
  return ALERT_STATUS_MAP[status] || { type: 'info', label: status }
}

async function loadEvents() {
  loading.value = true
  try {
    const data = await listAlertsApi(query)
    events.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

async function openDetail(row) {
  detail.value = await getAlertApi(row.id)
  detailVisible.value = true
}

async function handleAck(row) {
  await ackAlertApi(row.id)
  ElMessage.success('已确认')
  await loadEvents()
}

async function handleResolve(row) {
  await resolveAlertApi(row.id)
  ElMessage.success('已恢复')
  await loadEvents()
}

// ---------- 规则管理 ----------
const rules = ref([])
const ruleDialog = ref(false)
const ruleMode = ref('create')
const ruleForm = reactive({
  id: null,
  rule_name: '',
  metric_type: 'CPU',
  severity: 'WARNING',
  operator: 'GT',
  threshold: 80,
  duration_seconds: 0,
  enabled: 1,
  description: '',
})

async function loadRules() {
  rules.value = await listRulesApi()
}

function openRuleCreate() {
  ruleMode.value = 'create'
  Object.assign(ruleForm, {
    id: null, rule_name: '', metric_type: 'CPU', severity: 'WARNING',
    operator: 'GT', threshold: 80, duration_seconds: 0, enabled: 1, description: '',
  })
  ruleDialog.value = true
}

function openRuleEdit(row) {
  ruleMode.value = 'edit'
  Object.assign(ruleForm, row)
  ruleDialog.value = true
}

async function handleRuleSubmit() {
  const payload = { ...ruleForm }
  delete payload.id
  if (ruleMode.value === 'create') {
    await createRuleApi(payload)
    ElMessage.success('创建成功')
  } else {
    await updateRuleApi(ruleForm.id, payload)
    ElMessage.success('更新成功')
  }
  ruleDialog.value = false
  await loadRules()
}

async function handleRuleDelete(row) {
  await ElMessageBox.confirm(`确定删除规则「${row.rule_name}」吗？`, '提示', { type: 'warning' })
  await deleteRuleApi(row.id)
  ElMessage.success('删除成功')
  await loadRules()
}

function switchTab(tab) {
  if (tab === 'rules') loadRules()
  else loadEvents()
}

onMounted(loadEvents)
</script>

<template>
  <el-card shadow="never">
    <el-tabs v-model="activeTab" @tab-change="switchTab">
      <!-- 告警事件 -->
      <el-tab-pane label="告警事件" name="events">
        <div class="toolbar">
          <el-form inline @submit.prevent>
            <el-form-item label="级别">
              <el-select v-model="query.severity" clearable placeholder="全部" style="width: 110px">
                <el-option v-for="(v, k) in ALERT_SEVERITY_MAP" :key="k" :label="v.label" :value="k" />
              </el-select>
            </el-form-item>
            <el-form-item label="状态">
              <el-select v-model="query.status" clearable placeholder="全部" style="width: 110px">
                <el-option v-for="(v, k) in ALERT_STATUS_MAP" :key="k" :label="v.label" :value="k" />
              </el-select>
            </el-form-item>
            <el-form-item label="类型">
              <el-select v-model="query.active" clearable placeholder="全部" style="width: 110px">
                <el-option label="仅活动" :value="true" />
                <el-option label="仅历史" :value="false" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="loadEvents">查询</el-button>
            </el-form-item>
          </el-form>
        </div>

        <el-table :data="events" v-loading="loading">
          <el-table-column prop="severity" label="级别" width="80">
            <template #default="{ row }">
              <el-tag :type="severityOf(row.severity).type" size="small">{{ severityOf(row.severity).label }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="statusOf(row.status).type" size="small">{{ statusOf(row.status).label }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="rule_name" label="规则" min-width="150" />
          <el-table-column prop="server_hostname" label="服务器" min-width="120" />
          <el-table-column prop="metric_type" label="指标" width="90" />
          <el-table-column label="当前值 / 阈值" width="140">
            <template #default="{ row }">{{ row.current_value ?? '-' }} / {{ row.threshold_value ?? '-' }}</template>
          </el-table-column>
          <el-table-column prop="message" label="消息" min-width="200" show-overflow-tooltip />
          <el-table-column label="最近触发" min-width="150">
            <template #default="{ row }">{{ formatTime(row.last_fired_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="190" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openDetail(row)">详情</el-button>
              <template v-if="canOperate() && row.status !== 'RESOLVED'">
                <el-button link type="warning" @click="handleAck(row)" v-if="row.status !== 'ACKNOWLEDGED'">确认</el-button>
                <el-button link type="success" @click="handleResolve(row)">恢复</el-button>
              </template>
            </template>
          </el-table-column>
        </el-table>

        <el-pagination
          class="pagination"
          layout="total, prev, pager, next"
          :total="total"
          v-model:current-page="query.page"
          v-model:page-size="query.page_size"
          @current-change="loadEvents"
        />
      </el-tab-pane>

      <!-- 告警规则 -->
      <el-tab-pane label="告警规则" name="rules">
        <div class="toolbar">
          <el-button v-if="userStore.isAdmin" type="primary" @click="openRuleCreate">新增规则</el-button>
        </div>
        <el-table :data="rules">
          <el-table-column prop="rule_name" label="规则名称" min-width="150" />
          <el-table-column prop="metric_type" label="指标" width="90" />
          <el-table-column prop="severity" label="级别" width="80">
            <template #default="{ row }">
              <el-tag :type="severityOf(row.severity).type" size="small">{{ severityOf(row.severity).label }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="条件" min-width="140">
            <template #default="{ row }">{{ row.operator }} {{ row.threshold }}</template>
          </el-table-column>
          <el-table-column prop="duration_seconds" label="持续(秒)" width="90" />
          <el-table-column label="启用" width="80">
            <template #default="{ row }">
              <el-switch :model-value="row.enabled === 1" disabled />
            </template>
          </el-table-column>
          <el-table-column prop="description" label="描述" min-width="180" show-overflow-tooltip />
          <el-table-column label="操作" width="140" fixed="right" v-if="userStore.isAdmin">
            <template #default="{ row }">
              <el-button link type="primary" @click="openRuleEdit(row)">编辑</el-button>
              <el-button link type="danger" @click="handleRuleDelete(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <!-- 事件详情 -->
    <el-dialog v-model="detailVisible" title="告警详情" width="600px">
      <template v-if="detail">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="规则">{{ detail.event.rule_name }}</el-descriptions-item>
          <el-descriptions-item label="级别">{{ detail.event.severity }}</el-descriptions-item>
          <el-descriptions-item label="服务器">{{ detail.event.server_hostname || '-' }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ statusOf(detail.event.status).label }}</el-descriptions-item>
          <el-descriptions-item label="指标">{{ detail.event.metric_type }}</el-descriptions-item>
          <el-descriptions-item label="当前值 / 阈值">{{ detail.event.current_value }} / {{ detail.event.threshold_value }}</el-descriptions-item>
          <el-descriptions-item label="首次触发">{{ formatTime(detail.event.first_fired_at) }}</el-descriptions-item>
          <el-descriptions-item label="恢复时间">{{ formatTime(detail.event.resolved_at) }}</el-descriptions-item>
          <el-descriptions-item label="消息" :span="2">{{ detail.event.message }}</el-descriptions-item>
        </el-descriptions>
        <el-timeline class="timeline">
          <el-timeline-item
            v-for="log in detail.logs"
            :key="log.id"
            :timestamp="formatTime(log.created_at)"
            :type="log.new_status === 'RESOLVED' ? 'success' : 'primary'"
          >
            {{ log.old_status || '触发' }} → {{ log.new_status }}：{{ log.message }}
          </el-timeline-item>
        </el-timeline>
      </template>
    </el-dialog>

    <!-- 规则编辑 -->
    <el-dialog v-model="ruleDialog" :title="ruleMode === 'create' ? '新增规则' : '编辑规则'" width="480px">
      <el-form :model="ruleForm" label-width="90px">
        <el-form-item label="规则名称" required>
          <el-input v-model="ruleForm.rule_name" />
        </el-form-item>
        <el-form-item label="指标类型" required>
          <el-select v-model="ruleForm.metric_type" style="width: 100%">
            <el-option v-for="m in ALERT_METRIC_TYPES" :key="m" :label="m" :value="m" />
          </el-select>
        </el-form-item>
        <el-form-item label="级别">
          <el-radio-group v-model="ruleForm.severity">
            <el-radio value="WARNING">警告</el-radio>
            <el-radio value="CRITICAL">严重</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="条件">
          <div class="condition">
            <el-select v-model="ruleForm.operator" style="width: 90px">
              <el-option v-for="op in ALERT_OPERATORS" :key="op" :label="op" :value="op" />
            </el-select>
            <el-input-number v-model="ruleForm.threshold" :min="0" :step="1" />
          </div>
        </el-form-item>
        <el-form-item label="持续(秒)">
          <el-input-number v-model="ruleForm.duration_seconds" :min="0" :step="10" />
          <span class="tip">PENDING 持续该时长后升级 FIRING</span>
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="ruleForm.enabled" :active-value="1" :inactive-value="0" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="ruleForm.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="ruleDialog = false">取消</el-button>
        <el-button type="primary" @click="handleRuleSubmit">确定</el-button>
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
.timeline {
  margin-top: 16px;
}
.condition {
  display: flex;
  align-items: center;
  gap: 8px;
}
.tip {
  margin-left: 8px;
  color: #909399;
  font-size: 12px;
}
</style>
