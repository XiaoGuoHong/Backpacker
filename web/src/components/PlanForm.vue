<script setup lang="ts">
import { reactive, ref } from 'vue'
import type { BudgetLevel, HotelType, TripRequest } from '../types'

const emit = defineEmits<{ (e: 'submit', req: TripRequest): void }>()

const INTERESTS = [
  { k: '历史文化', icon: '🏛' },
  { k: '自然风光', icon: '🏞' },
  { k: '美食', icon: '🍜' },
  { k: '购物', icon: '🛍' },
  { k: '夜生活', icon: '🌃' },
  { k: '亲子', icon: '🐧' },
  { k: '摄影', icon: '📷' },
  { k: '艺术', icon: '🎨' },
]

const BUDGET = [
  { k: 'low', label: '经济', sub: '性价比' },
  { k: 'mid', label: '舒适', sub: '平衡' },
  { k: 'high', label: '豪华', sub: '极致' },
]

const HOTELS = [
  { k: '经济型', sub: '~200/晚' },
  { k: '舒适型', sub: '~400/晚' },
  { k: '豪华型', sub: '~900/晚' },
]

const form = reactive({
  destination: '北京',
  startDate: '',
  days: 3,
  budgetLevel: 'mid' as BudgetLevel,
  interests: ['历史文化', '美食'] as string[],
  hotelType: '舒适型' as HotelType,
})

const error = ref('')

function toggleInterest(i: string) {
  const idx = form.interests.indexOf(i)
  if (idx >= 0) form.interests.splice(idx, 1)
  else form.interests.push(i)
}

function pickBudget(k: BudgetLevel) {
  form.budgetLevel = k
}
function pickHotel(k: HotelType) {
  form.hotelType = k
}

function submit() {
  error.value = ''
  if (!form.destination.trim()) {
    error.value = '请填写目的地'
    return
  }
  if (!form.startDate) {
    error.value = '请选择开始日期'
    return
  }
  if (form.interests.length === 0) {
    error.value = '请至少选择一项兴趣偏好'
    return
  }
  emit('submit', {
    destination: form.destination.trim(),
    start_date: form.startDate,
    days: Number(form.days) || 1,
    budget_level: form.budgetLevel,
    interests: [...form.interests],
    hotel_type: form.hotelType,
  })
}
</script>

<template>
  <div class="form glass">
    <h2 class="title">规划行程</h2>

    <div class="field">
      <label>目的地</label>
      <input v-model="form.destination" placeholder="例如：北京、上海、成都" />
    </div>

    <div class="grid-2">
      <div class="field">
        <label>开始日期</label>
        <input type="date" v-model="form.startDate" />
      </div>
      <div class="field">
        <label>天数</label>
        <div class="stepper">
          <button class="step" type="button" @click="form.days = Math.max(1, form.days - 1)">−</button>
          <span class="step-val">{{ form.days }}</span>
          <button class="step" type="button" @click="form.days = Math.min(30, form.days + 1)">+</button>
        </div>
      </div>
    </div>

    <div class="field">
      <label>兴趣偏好</label>
      <div class="chips">
        <button
          v-for="it in INTERESTS"
          :key="it.k"
          type="button"
          class="chip"
          :class="{ active: form.interests.includes(it.k) }"
          @click="toggleInterest(it.k)"
        >
          <span class="chip-icon">{{ it.icon }}</span>
          <span class="chip-text">{{ it.k }}</span>
        </button>
      </div>
    </div>

    <div class="field">
      <label>预算档位</label>
      <div class="segmented">
        <button
          v-for="b in BUDGET"
          :key="b.k"
          type="button"
          class="seg"
          :class="{ active: form.budgetLevel === b.k }"
          @click="pickBudget(b.k as BudgetLevel)"
        >
          <span class="seg-title">{{ b.label }}</span>
          <span class="seg-sub">{{ b.sub }}</span>
        </button>
      </div>
    </div>

    <div class="field">
      <label>酒店类型</label>
      <div class="segmented">
        <button
          v-for="h in HOTELS"
          :key="h.k"
          type="button"
          class="seg"
          :class="{ active: form.hotelType === h.k }"
          @click="pickHotel(h.k as HotelType)"
        >
          <span class="seg-title">{{ h.k }}</span>
          <span class="seg-sub">{{ h.sub }}</span>
        </button>
      </div>
    </div>

    <p v-if="error" class="error">{{ error }}</p>

    <button class="primary" type="button" @click="submit">
      <span class="primary-label">生成行程</span>
      <span class="primary-arrow">→</span>
    </button>
  </div>
</template>

<style scoped>
.form {
  border-radius: var(--radius-xl);
  padding: 32px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  background: var(--glass);
  backdrop-filter: blur(20px) saturate(1.4);
  -webkit-backdrop-filter: blur(20px) saturate(1.4);
  border: 1px solid var(--glass-border);
  box-shadow: var(--shadow-2);
}
.title {
  margin: 0 0 4px;
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.02em;
}
.field { display: flex; flex-direction: column; gap: 8px; }
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
label {
  font-size: 12px;
  letter-spacing: 0.04em;
  color: var(--muted);
  text-transform: uppercase;
  font-weight: 500;
}
input {
  padding: 12px 14px;
  border: 1px solid var(--glass-border);
  border-radius: var(--radius);
  background: rgba(255, 255, 255, 0.05);
  color: var(--text);
  font-size: 15px;
  transition: all 0.18s ease;
}
input:focus {
  outline: none;
  border-color: var(--accent);
  background: rgba(10, 132, 255, 0.06);
  box-shadow: 0 0 0 3px rgba(10, 132, 255, 0.18);
}
input::-webkit-calendar-picker-indicator { filter: invert(0.9); cursor: pointer; }

.stepper {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  border: 1px solid var(--glass-border);
  border-radius: var(--radius);
  background: rgba(255, 255, 255, 0.05);
}
.step {
  width: 32px; height: 32px;
  border-radius: 50%;
  border: 1px solid var(--glass-border);
  background: rgba(255, 255, 255, 0.08);
  color: var(--text);
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
  transition: all 0.18s ease;
}
.step:hover { background: rgba(255, 255, 255, 0.18); }
.step-val { font-size: 18px; font-weight: 600; }

.chips { display: flex; flex-wrap: wrap; gap: 10px; }
.chip {
  display: flex; align-items: center; gap: 6px;
  padding: 8px 14px;
  border-radius: var(--radius-pill);
  border: 1px solid var(--glass-border);
  background: rgba(255, 255, 255, 0.05);
  color: var(--text-2);
  cursor: pointer;
  font-size: 13.5px;
  font-weight: 500;
  transition: all 0.18s ease;
}
.chip:hover { background: rgba(255, 255, 255, 0.10); }
.chip.active {
  background: linear-gradient(135deg, var(--accent), var(--accent-2));
  border-color: transparent;
  color: #fff;
  box-shadow: 0 4px 14px rgba(10, 132, 255, 0.35);
}
.chip-icon { font-size: 16px; }

.segmented {
  display: grid;
  grid-auto-flow: column;
  grid-auto-columns: 1fr;
  gap: 4px;
  padding: 4px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius);
}
.seg {
  display: flex; flex-direction: column; align-items: center; gap: 2px;
  padding: 9px 6px;
  border: none;
  border-radius: calc(var(--radius) - 4px);
  background: transparent;
  color: var(--muted);
  cursor: pointer;
  transition: all 0.16s ease;
}
.seg:hover { color: var(--text-2); }
.seg.active {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.14), rgba(255, 255, 255, 0.06));
  color: var(--text);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.18), inset 0 0 0 1px rgba(255, 255, 255, 0.10);
}
.seg-title { font-size: 14px; font-weight: 600; }
.seg-sub { font-size: 11px; color: var(--muted-2); }
.seg.active .seg-sub { color: var(--text-2); }

.error {
  margin: 0;
  padding: 10px 14px;
  background: rgba(255, 69, 58, 0.12);
  border: 1px solid rgba(255, 69, 58, 0.32);
  border-radius: var(--radius);
  color: #ffccc8;
  font-size: 13.5px;
}

.primary {
  margin-top: 4px;
  padding: 14px 22px;
  border: none;
  border-radius: var(--radius);
  background: linear-gradient(135deg, var(--accent) 0%, var(--accent-2) 100%);
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  letter-spacing: -0.01em;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  box-shadow: 0 6px 18px rgba(10, 132, 255, 0.35);
  transition: all 0.18s ease;
}
.primary:hover {
  transform: translateY(-1px);
  box-shadow: 0 10px 28px rgba(10, 132, 255, 0.45);
}
.primary:active { transform: translateY(0); }
.primary-arrow { transition: transform 0.18s ease; }
.primary:hover .primary-arrow { transform: translateX(4px); }
</style>