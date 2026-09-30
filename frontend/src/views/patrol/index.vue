<template>
  <section class="page" data-module="patrol">
    <header class="page-head">
      <div>
        <h2>巡查任务管理</h2>
        <p class="page-desc">维护巡查单，围绕巡查单号、巡查路线、巡查人员、巡查日期做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记巡查单</button>
        <button class="btn" type="button" @click="exportRows">导出巡查任务清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in statsCards" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <nav class="group-tabs" aria-label="巡查单分组">
      <button
        v-for="tab in groupTabs"
        :key="tab.status"
        class="group-tab"
        :class="{ active: activeGroup === tab.status }"
        type="button"
        @click="switchGroup(tab.status)"
      >
        {{ tab.label }}
        <span class="group-count">{{ groupCount(tab.status) }}</span>
      </button>
    </nav>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>巡查单号</span>
        <input v-model="keyword" placeholder="按巡查单号检索" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in tableColumns" :key="column">{{ column }}</th>
          <th v-if="activeGroup === '已作废'">作废原因</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in tableColumns" :key="column">{{ formatCell(row, column) }}</td>
          <td v-if="activeGroup === '已作废'">{{ row['作废原因'] ?? '—' }}</td>
          <td class="row-actions">
            <button class="link" type="button" @click="openDetail(row)">查看详情</button>
            <button
              v-if="row['巡查状态'] === '待派发'"
              class="link"
              type="button"
              @click="dispatch(row)"
            >
              派发巡查
            </button>
            <button
              v-if="row['巡查状态'] === '巡查中'"
              class="link"
              type="button"
              @click="openSubmit(row)"
            >
              提交结果
            </button>
            <button
              v-if="row['巡查状态'] === '待派发' || row['巡查状态'] === '巡查中'"
              class="link danger"
              type="button"
              @click="openVoid(row)"
            >
              作废巡查
            </button>
            <span v-if="isTerminal(row)" class="action-muted">
              {{ row['巡查状态'] === '已作废' ? '已归档历史' : '流程已完结' }}
            </span>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="tableColumns.length + (activeGroup === '已作废' ? 2 : 1)" class="empty-state">
            当前分组暂无巡查任务数据
          </td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条{{ groupLabel(activeGroup) }}巡查单</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <!-- 登记巡查单 -->
    <div v-if="dialog === 'create'" class="modal-mask" @click.self="closeDialog">
      <form class="modal" @submit.prevent="submitCreate">
        <h3 class="modal-title">登记巡查单</h3>
        <label class="form-item">
          <span>巡查单号 *</span>
          <input v-model="createForm.巡查单号" placeholder="如 PATR-0005" />
        </label>
        <label class="form-item">
          <span>巡查路线 *</span>
          <input v-model="createForm.巡查路线" placeholder="起终点或路段名称" />
        </label>
        <label class="form-item">
          <span>巡查人员 *</span>
          <input v-model="createForm.巡查人员" placeholder="负责巡查的人员" />
        </label>
        <label class="form-item">
          <span>巡查日期</span>
          <input v-model="createForm.巡查日期" type="date" />
        </label>
        <p v-if="formError" class="error-text">{{ formError }}</p>
        <div class="modal-actions">
          <button class="btn ghost" type="button" @click="closeDialog">取消</button>
          <button class="btn primary" type="submit">确认登记</button>
        </div>
      </form>
    </div>

    <!-- 提交结果 -->
    <div v-if="dialog === 'submit'" class="modal-mask" @click.self="closeDialog">
      <form class="modal" @submit.prevent="submitResult">
        <h3 class="modal-title">提交巡查结果 · {{ activeRow?.['巡查单号'] }}</h3>
        <p class="modal-hint">状态只能由「巡查中」推进到「已提交」，提交后结果不可重复提交或覆盖。</p>
        <label class="form-item">
          <span>巡查路线 *</span>
          <input v-model="submitForm.巡查路线" placeholder="实际巡查路线" />
        </label>
        <label class="form-item">
          <span>发现问题数 *</span>
          <input v-model="submitForm.发现问题数" type="number" min="0" step="1" placeholder="非负整数" />
        </label>
        <label class="form-item">
          <span>巡查里程（公里）</span>
          <input v-model="submitForm.巡查里程" type="number" min="0" step="0.1" placeholder="不填按 0 计" />
        </label>
        <label class="form-item">
          <span>巡查时长</span>
          <input v-model="submitForm.巡查时长" placeholder="如 2.5小时" />
        </label>
        <p v-if="formError" class="error-text">{{ formError }}</p>
        <div class="modal-actions">
          <button class="btn ghost" type="button" @click="closeDialog">取消</button>
          <button class="btn primary" type="submit">确认提交</button>
        </div>
      </form>
    </div>

    <!-- 作废巡查 -->
    <div v-if="dialog === 'void'" class="modal-mask" @click.self="closeDialog">
      <form class="modal" @submit.prevent="submitVoid">
        <h3 class="modal-title">作废巡查单 · {{ activeRow?.['巡查单号'] }}</h3>
        <p class="modal-hint">作废后该单转入历史分组、不再计入统计，且不可恢复。</p>
        <label class="form-item">
          <span>作废原因 *</span>
          <textarea v-model="voidReason" rows="3" placeholder="请说明作废原因"></textarea>
        </label>
        <p v-if="formError" class="error-text">{{ formError }}</p>
        <div class="modal-actions">
          <button class="btn ghost" type="button" @click="closeDialog">取消</button>
          <button class="btn danger" type="submit">确认作废</button>
        </div>
      </form>
    </div>

    <!-- 巡查单详情 -->
    <div v-if="dialog === 'detail' && activeRow" class="modal-mask" @click.self="closeDialog">
      <div class="modal">
        <h3 class="modal-title">巡查单详情 · {{ activeRow['巡查单号'] }}</h3>
        <dl class="detail-grid">
          <template v-for="field in detailFields" :key="field">
            <dt>{{ field }}</dt>
            <dd>{{ formatCell(activeRow, field) }}</dd>
          </template>
          <template v-if="activeRow['巡查状态'] === '已作废'">
            <dt>作废原因</dt>
            <dd>{{ activeRow['作废原因'] ?? '—' }}</dd>
            <dt>作废日期</dt>
            <dd>{{ activeRow['作废日期'] ?? '—' }}</dd>
          </template>
          <template v-if="activeRow['巡查状态'] === '已提交'">
            <dt>提交日期</dt>
            <dd>{{ activeRow['提交日期'] ?? '—' }}</dd>
          </template>
        </dl>
        <div class="modal-actions">
          <button class="btn primary" type="button" @click="closeDialog">关闭</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>
type DialogType = '' | 'create' | 'submit' | 'void' | 'detail'
type GroupStatus = '全部' | '待派发' | '巡查中' | '已提交' | '已作废'

const ENDPOINT = '/api/patrol'
const GROUP_STORAGE_KEY = 'patrol:active-group'
const groupTabs: { status: GroupStatus; label: string }[] = [
  { status: '全部', label: '全部' },
  { status: '待派发', label: '待派发' },
  { status: '巡查中', label: '巡查中' },
  { status: '已提交', label: '已提交台账' },
  { status: '已作废', label: '历史（已作废）' },
]

const baseColumns = ['巡查单号', '巡查路线', '巡查人员', '巡查日期', '巡查里程', '发现问题数', '巡查时长']
const tableColumns = [...baseColumns, '巡查状态']

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const keyword = ref('')

// 汇总卡片与台账同源：后端按已提交巡查单合计，作废单不计入。
const statsCards = ref([
  { label: '待派发巡查', value: 0 },
  { label: '巡查中任务', value: 0 },
  { label: '累计巡查里程（公里）', value: '0' },
  { label: '累计发现问题（个）', value: 0 },
])
const statusCounts = ref<Record<string, number>>({})

const dialog = ref<DialogType>('')
const activeRow = ref<Row | null>(null)
const formError = ref('')
const createForm = ref({ 巡查单号: '', 巡查路线: '', 巡查人员: '', 巡查日期: '' })
const submitForm = ref({ 巡查路线: '', 发现问题数: '', 巡查里程: '', 巡查时长: '' })
const voidReason = ref('')

const savedGroup = window.localStorage.getItem(GROUP_STORAGE_KEY) as GroupStatus | null
const activeGroup = ref<GroupStatus>(
  savedGroup && groupTabs.some((tab) => tab.status === savedGroup) ? savedGroup : '全部',
)

function groupCount(status: GroupStatus): number | string {
  if (status === '全部') {
    return groupTabs
      .filter((tab) => tab.status !== '全部')
      .reduce((sum, tab) => sum + (statusCounts.value[tab.status] ?? 0), 0)
  }
  return statusCounts.value[status] ?? 0
}

function groupLabel(status: GroupStatus): string {
  return status === '全部' ? '' : status
}

function isTerminal(row: Row): boolean {
  const status = String(row['巡查状态'] ?? '')
  return status === '已提交' || status === '已作废'
}

function formatCell(row: Row, column: string): string | number {
  const value = row[column]
  if (column === '巡查里程' && (value === null || value === '' || value === undefined)) {
    return statusPending(row) ? '—' : 0
  }
  if (column === '发现问题数' && (value === null || value === '' || value === undefined)) {
    return statusPending(row) ? '—' : 0
  }
  if (value === null || value === undefined || value === '') return '—'
  return value as string | number
}

function statusPending(row: Row): boolean {
  const status = String(row['巡查状态'] ?? '')
  return status === '待派发' || status === '巡查中'
}

const detailFields = [...baseColumns, '巡查状态']

function switchGroup(status: GroupStatus) {
  activeGroup.value = status
  window.localStorage.setItem(GROUP_STORAGE_KEY, status)
  void reload()
}

function resetFilters() {
  keyword.value = ''
  void reload()
}

function exportRows() {
  const query = new URLSearchParams()
  if (keyword.value) query.set('keyword', keyword.value)
  if (activeGroup.value !== '全部') query.set('status', activeGroup.value)
  window.open(`${ENDPOINT}/export?${query.toString()}`, '_blank')
}

function closeDialog() {
  dialog.value = ''
  activeRow.value = null
  formError.value = ''
}

function openCreate() {
  createForm.value = { 巡查单号: '', 巡查路线: '', 巡查人员: '', 巡查日期: '' }
  formError.value = ''
  dialog.value = 'create'
}

function openSubmit(row: Row) {
  activeRow.value = row
  submitForm.value = {
    巡查路线: String(row['巡查路线'] ?? ''),
    发现问题数: '',
    巡查里程: '',
    巡查时长: '',
  }
  formError.value = ''
  dialog.value = 'submit'
}

function openVoid(row: Row) {
  activeRow.value = row
  voidReason.value = ''
  formError.value = ''
  dialog.value = 'void'
}

function openDetail(row: Row) {
  activeRow.value = row
  formError.value = ''
  dialog.value = 'detail'
}

async function postAction(body: Record<string, unknown>): Promise<boolean> {
  const response = await request(`${ENDPOINT}/${activeRow.value?.id ?? ''}/actions`, {
    method: 'POST',
    body: JSON.stringify(body),
  })
  const payload = (await response.json().catch(() => null)) as { ok?: boolean; message?: string } | null
  if (!response.ok || !payload?.ok) {
    formError.value = payload?.message || '巡查任务动作未生效，请稍后重试'
    return false
  }
  closeDialog()
  await Promise.all([reload(), loadStats()])
  return true
}

async function submitCreate() {
  formError.value = ''
  const values: Record<string, string> = {
    巡查单号: createForm.value.巡查单号.trim(),
    巡查路线: createForm.value.巡查路线.trim(),
    巡查人员: createForm.value.巡查人员.trim(),
  }
  if (createForm.value.巡查日期) values.巡查日期 = createForm.value.巡查日期
  if (!values.巡查单号 || !values.巡查路线 || !values.巡查人员) {
    formError.value = '巡查单号、巡查路线、巡查人员为必填项'
    return
  }
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values }),
    })
    const payload = (await response.json().catch(() => null)) as { ok?: boolean; message?: string } | null
    if (!response.ok || !payload?.ok) {
      formError.value = payload?.message || '巡查单登记失败'
      return
    }
    closeDialog()
    await Promise.all([reload(), loadStats()])
  } catch (error) {
    formError.value = error instanceof Error ? error.message : '巡查单登记失败'
  }
}

async function dispatch(row: Row) {
  errorMessage.value = ''
  activeRow.value = row
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action: '派发巡查' } }),
    })
    const payload = (await response.json().catch(() => null)) as { ok?: boolean; message?: string } | null
    if (!response.ok || !payload?.ok) {
      errorMessage.value = payload?.message || '派发失败，请稍后重试'
    }
    await Promise.all([reload(), loadStats()])
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '巡查任务操作失败'
  } finally {
    activeRow.value = null
  }
}

function submitResult() {
  const values = {
    action: '提交结果',
    巡查路线: submitForm.value.巡查路线.trim(),
    发现问题数: submitForm.value.发现问题数.trim(),
    巡查里程: submitForm.value.巡查里程.trim(),
    巡查时长: submitForm.value.巡查时长.trim(),
  }
  void postAction({ values })
}

function submitVoid() {
  if (!voidReason.value.trim()) {
    formError.value = '作废必须填写原因'
    return
  }
  void postAction({ values: { action: '作废巡查', 作废原因: voidReason.value.trim() } })
}

async function loadStats() {
  try {
    const response = await request(`${ENDPOINT}/stats`)
    if (!response.ok) return
    const payload = (await response.json()) as {
      counts: Record<string, number>
      total_mileage: number
      total_issues: number
    }
    statusCounts.value = payload.counts ?? {}
    statsCards.value = [
      { label: '待派发巡查', value: payload.counts?.['待派发'] ?? 0 },
      { label: '巡查中任务', value: payload.counts?.['巡查中'] ?? 0 },
      { label: '累计巡查里程（公里）', value: Number(payload.total_mileage ?? 0).toFixed(1) },
      { label: '累计发现问题（个）', value: payload.total_issues ?? 0 },
    ]
  } catch {
    // 统计读不出来时保留上一次的卡片值，不打断主列表操作。
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  if (keyword.value.trim()) query.set('keyword', keyword.value.trim())
  if (activeGroup.value !== '全部') query.set('status', activeGroup.value)
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    if (!response.ok) {
      throw new Error('巡查单列表读取失败')
    }
    const payload = (await response.json()) as { items?: Row[]; total?: number }
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '巡查任务列表读取失败'
  }
}

onMounted(() => {
  void loadStats()
  void reload()
})
</script>

<style scoped>
.group-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.group-tab {
  border: 1px solid var(--border);
  background: #fff;
  border-radius: 16px;
  padding: 5px 14px;
  font-size: 13px;
  cursor: pointer;
  color: #334155;
}
.group-tab.active {
  background: var(--brand);
  border-color: var(--brand);
  color: #fff;
}
.group-count {
  margin-left: 4px;
  font-size: 12px;
  opacity: 0.75;
}
.action-muted {
  color: var(--muted);
  font-size: 12px;
}
.link.danger {
  color: #b42318;
}
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 20;
}
.modal {
  background: #fff;
  border-radius: 10px;
  width: 420px;
  max-width: calc(100vw - 32px);
  max-height: calc(100vh - 48px);
  overflow-y: auto;
  padding: 18px 20px;
}
.modal-title {
  margin: 0 0 12px;
  font-size: 16px;
}
.modal-hint {
  margin: 0 0 12px;
  font-size: 12px;
  color: var(--muted);
}
.form-item {
  display: block;
  margin-bottom: 10px;
  font-size: 13px;
}
.form-item span {
  display: block;
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 4px;
}
.form-item input,
.form-item textarea {
  width: 100%;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 8px;
  font: inherit;
}
.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 14px;
}
.btn.danger {
  background: #b42318;
  border-color: #b42318;
  color: #fff;
}
.detail-grid {
  display: grid;
  grid-template-columns: 96px 1fr;
  gap: 6px 12px;
  margin: 0;
  font-size: 13px;
}
.detail-grid dt {
  color: var(--muted);
}
.detail-grid dd {
  margin: 0;
}
</style>
