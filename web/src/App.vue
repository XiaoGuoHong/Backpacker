<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import PlanForm from './components/PlanForm.vue'
import Progress from './components/Progress.vue'
import ItineraryDay from './components/ItineraryDay.vue'
import MapView from './components/MapView.vue'
import BudgetPanel from './components/BudgetPanel.vue'
import SidebarNav from './components/SidebarNav.vue'
import ExportBar from './components/ExportBar.vue'
import {
  fetchConfig,
  fetchHealth,
  fetchItinerary,
  fetchMetrics,
  plan,
  pollItinerary,
  subscribeEvents,
} from './api'
import type {
  BudgetBreakdown,
  ItineraryDay as ItineraryDayType,
  PlanResult,
  TripRequest,
} from './types'

type Phase = 'form' | 'progress' | 'result'

const phase = ref<Phase>('form')
const stage = ref('')
const progressMsg = ref('')
const errorMsg = ref('')
const result = ref<PlanResult | null>(null)
const amapJsKey = ref<string | null>(null)

const health = ref<{ status: string; text: string }>({ status: '', text: '健康检测中…' })
const metricsText = ref('指标加载中…')

const editable = computed(() => phase.value === 'result' && result.value?.status !== 'failed')
const days = computed<ItineraryDayType[]>(() => result.value?.itinerary?.days || [])
const budget = computed<BudgetBreakdown>(
  () =>
    result.value?.itinerary?.budget || {
      ticket: 0,
      hotel: 0,
      food: 0,
      transport: 0,
      total: 0,
      currency: 'CNY',
    },
)
const activeDay = ref(1)

let timer: number | undefined

async function startPlan(req: TripRequest) {
  phase.value = 'progress'
  errorMsg.value = ''
  progressMsg.value = '提交行程请求…'
  stage.value = 'submitting'
  try {
    const accepted = await plan(req)
    stage.value = 'searching_attractions'
    subscribeEvents(accepted.task_id, {
      onStage: (s, msg) => {
        stage.value = s
        progressMsg.value = msg
      },
      onError: (msg) => {
        errorMsg.value = msg
      },
    })
    const polled = await pollItinerary(accepted.task_id, 120000)
    const final = polled || (await fetchItinerary(accepted.task_id))
    if (!final) {
      errorMsg.value = '未能获取行程结果'
      phase.value = 'form'
      return
    }
    result.value = final
    activeDay.value = final.itinerary?.days[0]?.index || 1
    phase.value = 'result'
  } catch (e) {
    errorMsg.value = e instanceof Error ? e.message : '规划请求失败'
    phase.value = 'form'
  }
}

function recomputeBudget(): BudgetBreakdown {
  const daysList = result.value?.itinerary?.days || []
  let ticket = 0
  let hotel = 0
  daysList.forEach((d) => {
    d.attractions.forEach((a) => {
      ticket += a.ticket_price || 0
    })
    if (d.hotel?.price_per_night) hotel += d.hotel.price_per_night
  })
  const base = result.value?.itinerary?.budget
  const food = base?.food || 0
  const transport = base?.transport || 0
  const currency = base?.currency || 'CNY'
  return { ticket, hotel, food, transport, total: ticket + hotel + food + transport, currency }
}

function removeAttraction(dayIndex: number, attrIndex: number) {
  const day = result.value?.itinerary?.days.find((d) => d.index === dayIndex)
  if (!day) return
  day.attractions.splice(attrIndex, 1)
  if (result.value?.itinerary) result.value.itinerary.budget = recomputeBudget()
}

function reorderAttraction(dayIndex: number, from: number, to: number) {
  const day = result.value?.itinerary?.days.find((d) => d.index === dayIndex)
  if (!day) return
  const [moved] = day.attractions.splice(from, 1)
  day.attractions.splice(to, 0, moved)
}

function scrollToDay(index: number) {
  activeDay.value = index
  const el = document.getElementById(`day-${index}`)
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function reset() {
  phase.value = 'form'
  result.value = null
  errorMsg.value = ''
  progressMsg.value = ''
  stage.value = ''
}

async function refreshStatus() {
  try {
    const h = await fetchHealth()
    const ok = h.status === 'ok'
    health.value = { status: ok ? 'ok' : 'warn', text: ok ? '服务可用' : '服务降级' }
    const m = await fetchMetrics()
    const okCount = Object.values(m.by_type || {}).reduce((a, b) => a + (b.success || 0), 0)
    metricsText.value = `查询 ${m.total || 0} 次 / 成功 ${okCount}`
  } catch {
    health.value = { status: 'warn', text: '无法连接' }
  }
}

onMounted(async () => {
  refreshStatus()
  timer = window.setInterval(refreshStatus, 30000)
  try {
    const cfg = await fetchConfig()
    amapJsKey.value = cfg.amap_js_key
  } catch {
    amapJsKey.value = null
  }
})

onBeforeUnmount(() => {
  if (timer) window.clearInterval(timer)
})
</script>

<template>
  <div class="layout">
    <header class="topbar">
      <div class="brand">
        <span class="logo">🎒</span>
        <h1>Backpacker 智能旅行行程规划器</h1>
      </div>
      <div class="status">
        <span class="pill" :class="health.status">{{ health.text }}</span>
        <span class="pill">{{ metricsText }}</span>
      </div>
    </header>

    <main class="content">
      <div v-if="errorMsg" class="alert">
        <p>{{ errorMsg }}</p>
        <button class="ghost" @click="errorMsg = ''">关闭</button>
      </div>

      <!-- 表单页 -->
      <section v-if="phase === 'form'" class="form-panel">
        <PlanForm @submit="startPlan" />
      </section>

      <!-- 加载态 -->
      <section v-else-if="phase === 'progress'" class="progress-panel">
        <Progress :stage="stage" :message="progressMsg || '正在处理…'" />
      </section>

      <!-- 结果页 -->
      <section v-else class="result" :class="{ failed: result?.status === 'failed' }">
        <div v-if="result?.status === 'failed'" class="alert">
          <p>{{ result?.error_message || '行程规划失败，请重试。' }}</p>
          <button class="ghost" @click="reset">重新规划</button>
        </div>
        <div v-else class="result-grid" id="result-capture">
          <aside class="rail">
            <div class="result-head">
              <div>
                <span v-if="result?.condition_summary">{{ result.condition_summary }}</span>
                <span v-if="result?.itinerary?.is_demo" class="badge">演示数据</span>
              </div>
              <hr />
              <ExportBar />
              <button class="ghost full" @click="reset">重新规划</button>
            </div>
            <SidebarNav :days="days" :active="activeDay" @select="scrollToDay" />
          </aside>
          <div class="body">
            <MapView :days="days" :amap-js-key="amapJsKey" />
            <BudgetPanel :budget="budget" />
            <div v-if="result?.itinerary?.notes?.length" class="notes">
              <h3>说明</h3>
              <ul>
                <li v-for="(n, i) in result.itinerary.notes" :key="i">{{ n }}</li>
              </ul>
              <p v-if="result.hints" class="muted">{{ result.hints }}</p>
              <p v-if="result.request_id" class="muted">request_id: {{ result.request_id }}</p>
            </div>
            <div class="days">
              <ItineraryDay
                v-for="d in days"
                :key="d.index"
                :day="d"
                :editable="editable"
                @remove-attraction="(i) => removeAttraction(d.index, i)"
                @reorder="(from, to) => reorderAttraction(d.index, from, to)"
              />
            </div>
          </div>
        </div>
      </section>
    </main>
  </div>
</template>

<style scoped>
.layout { height: 100vh; display: flex; flex-direction: column; }
.topbar {
  padding: 10px 16px; background: var(--panel); display: flex; align-items: center;
  justify-content: space-between; border-bottom: 1px solid #0b1220; gap: 12px;
}
.brand { display: flex; align-items: center; gap: 10px; }
.logo { font-size: 20px; }
.topbar h1 { font-size: 16px; margin: 0; }
.status { display: flex; gap: 8px; }
.pill {
  font-size: 12px; padding: 3px 10px; border-radius: 999px; background: #0b1220; color: var(--muted);
}
.pill.ok { color: var(--ok); }
.pill.warn { color: var(--warn); }
.content { flex: 1; overflow-y: auto; padding: 20px; }
.form-panel { max-width: 560px; margin: 0 auto; background: var(--panel); border-radius: 12px; padding: 24px; }
.progress-panel { max-width: 560px; margin: 0 auto; }
.alert {
  background: var(--error); color: #fff; padding: 10px 14px; border-radius: 8px;
  margin: 8px auto 16px; max-width: 960px; display: flex; justify-content: space-between; align-items: center; gap: 12px;
}
.alert p { margin: 0; }
.result-grid { display: grid; grid-template-columns: 260px 1fr; gap: 16px; max-width: 1100px; margin: 0 auto; }
.rail { display: flex; flex-direction: column; gap: 12px; position: sticky; top: 20px; align-self: start; }
.result-head { background: var(--panel); border-radius: 12px; padding: 14px; display: flex; flex-direction: column; gap: 8px; font-size: 13px; }
.result-head hr { border: none; border-top: 1px solid var(--bubble); margin: 6px 0; }
.badge { background: var(--demo); color: #fff; font-size: 11px; padding: 2px 8px; border-radius: 999px; margin-left: 6px; }
.body { display: flex; flex-direction: column; gap: 16px; }
.days { display: flex; flex-direction: column; gap: 16px; }
.notes { background: var(--panel); border-radius: 12px; padding: 16px; font-size: 13px; }
.notes h3 { margin: 0 0 8px; }
.notes ul { margin: 0; padding-left: 18px; display: flex; flex-direction: column; gap: 4px; }
.muted { color: var(--muted); font-size: 12px; margin: 4px 0 0; }
.ghost {
  padding: 8px 14px; border: 1px solid var(--bubble); border-radius: 8px;
  background: var(--bg); color: var(--text); font-size: 13px; cursor: pointer;
}
.ghost.full { width: 100%; }
.ghost:hover { border-color: var(--user); }
@media (max-width: 760px) {
  .result-grid { grid-template-columns: 1fr; }
  .rail { position: static; }
}
</style>