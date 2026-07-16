<script setup lang="ts">
import { reactive, ref } from 'vue'
import type { BudgetLevel, HotelType, TripRequest } from '../types'

const emit = defineEmits<{ (e: 'submit', req: TripRequest): void }>()

const INTERESTS = ['历史文化', '自然风光', '美食', '购物', '夜生活', '亲子', '摄影', '艺术']

const form = reactive({
  destination: '',
  startDate: '',
  days: 3,
  budgetLevel: 'mid' as BudgetLevel,
  interests: ['历史文化'] as string[],
  hotelType: '舒适型' as HotelType,
})

const error = ref('')

function toggleInterest(i: string) {
  const idx = form.interests.indexOf(i)
  if (idx >= 0) form.interests.splice(idx, 1)
  else form.interests.push(i)
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
    error.value = '请至少选择一个兴趣偏好'
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
  <div class="plan-form">
    <h2>规划你的行程</h2>
    <div class="field">
      <label>目的地</label>
      <input v-model="form.destination" placeholder="例如：北京" />
    </div>
    <div class="row">
      <div class="field">
        <label>开始日期</label>
        <input type="date" v-model="form.startDate" />
      </div>
      <div class="field">
        <label>天数</label>
        <input type="number" min="1" max="30" v-model.number="form.days" />
      </div>
    </div>
    <div class="row">
      <div class="field">
        <label>预算档位</label>
        <select v-model="form.budgetLevel">
          <option value="low">经济</option>
          <option value="mid">舒适</option>
          <option value="high">豪华</option>
        </select>
      </div>
      <div class="field">
        <label>酒店类型</label>
        <select v-model="form.hotelType">
          <option value="经济型">经济型</option>
          <option value="舒适型">舒适型</option>
          <option value="豪华型">豪华型</option>
        </select>
      </div>
    </div>
    <div class="field">
      <label>兴趣偏好</label>
      <div class="chips">
        <button
          v-for="i in INTERESTS"
          :key="i"
          type="button"
          :class="['chip', form.interests.includes(i) ? 'active' : '']"
          @click="toggleInterest(i)"
        >{{ i }}</button>
      </div>
    </div>
    <p v-if="error" class="error">{{ error }}</p>
    <button class="primary" @click="submit">生成行程</button>
  </div>
</template>

<style scoped>
.plan-form { display: flex; flex-direction: column; gap: 12px; }
h2 { margin: 0 0 8px; }
.field { display: flex; flex-direction: column; gap: 6px; }
.row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
label { font-size: 13px; color: var(--muted); }
input, select {
  padding: 8px 10px; border: 1px solid var(--bubble); border-radius: 8px;
  background: var(--bg); color: var(--text); font-size: 14px;
}
.chips { display: flex; flex-wrap: wrap; gap: 8px; }
.chip {
  padding: 6px 12px; border: 1px solid var(--bubble); border-radius: 999px;
  background: var(--bg); color: var(--muted); cursor: pointer; font-size: 13px;
}
.chip.active { background: var(--user); color: #fff; border-color: var(--user); }
.error { color: #f87171; margin: 0; font-size: 13px; }
.primary {
  margin-top: 8px; padding: 10px 16px; border: none; border-radius: 8px;
  background: var(--user); color: #fff; font-size: 15px; cursor: pointer;
}
.primary:hover { filter: brightness(1.1); }
</style>