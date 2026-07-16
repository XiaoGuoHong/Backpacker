<script setup lang="ts">
import { ref } from 'vue'
import type { ItineraryDay as ItineraryDayType } from '../types'
import AttractionCard from './AttractionCard.vue'

defineProps<{ day: ItineraryDayType; editable?: boolean }>()
const emit = defineEmits<{
  (e: 'remove-attraction', index: number): void
  (e: 'reorder', from: number, to: number): void
}>()

const dragIndex = ref<number | null>(null)

function onDragStart(i: number) {
  dragIndex.value = i
}
function onDrop(target: number) {
  if (dragIndex.value === null || dragIndex.value === target) return
  emit('reorder', dragIndex.value, target)
  dragIndex.value = null
}
</script>

<template>
  <section class="day" :id="`day-${day.index}`">
    <header class="day-head">
      <span class="index">Day {{ day.index }}</span>
      <span class="date">{{ day.date }}</span>
    </header>
    <div v-if="day.weather" class="weather">
      {{ day.weather.day_desc || '—' }}
      <span v-if="day.weather.temp_min != null && day.weather.temp_max != null">
        {{ day.weather.temp_min }}～{{ day.weather.temp_max }}°C
      </span>
      <span v-if="day.weather.wind">{{ day.weather.wind }}</span>
    </div>
    <div class="attractions">
      <div
        v-for="(a, i) in day.attractions"
        :key="i"
        class="attr-row"
        :draggable="editable"
        @dragstart="onDragStart(i)"
        @dragover.prevent
        @drop="onDrop(i)"
      >
        <AttractionCard :attraction="a" />
        <button v-if="editable" class="remove" title="移除景点" @click="emit('remove-attraction', i)">✕</button>
      </div>
      <p v-if="day.attractions.length === 0" class="empty">暂无景点</p>
    </div>
    <div v-if="day.hotel" class="hotel">
      <span class="label">酒店</span>
      <span class="name">{{ day.hotel.name }}</span>
      <span v-if="day.hotel.price_per_night != null" class="price">
        {{ day.hotel.price_per_night }} 元/晚
      </span>
    </div>
  </section>
</template>

<style scoped>
.day { background: var(--panel); border-radius: 12px; padding: 16px; display: flex; flex-direction: column; gap: 12px; scroll-margin-top: 72px; }
.day-head { display: flex; align-items: center; gap: 12px; }
.index { font-weight: 700; color: var(--user); }
.date { color: var(--muted); font-size: 14px; }
.weather { font-size: 13px; color: var(--muted); display: flex; gap: 12px; flex-wrap: wrap; }
.attractions { display: flex; flex-direction: column; gap: 8px; }
.attr-row { display: flex; align-items: stretch; gap: 8px; }
.attr-row[draggable="true"] { cursor: grab; }
.remove { background: transparent; border: none; color: #f87171; cursor: pointer; font-size: 16px; padding: 0 8px; }
.hotel { display: flex; gap: 8px; align-items: baseline; font-size: 13px; padding-top: 8px; border-top: 1px solid var(--bubble); }
.label { color: var(--muted); }
.name { font-weight: 600; }
.price { color: var(--ok); }
.empty { color: var(--muted); margin: 0; font-size: 13px; }
</style>