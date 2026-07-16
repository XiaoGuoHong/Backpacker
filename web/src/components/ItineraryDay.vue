<script setup lang="ts">
import { computed, ref } from 'vue'
import type { ItineraryDay as ItineraryDayType } from '../types'
import AttractionCard from './AttractionCard.vue'

const props = defineProps<{ day: ItineraryDayType; editable?: boolean }>()
const emit = defineEmits<{
  (e: 'remove-attraction', index: number): void
  (e: 'reorder', from: number, to: number): void
}>()

const dragIndex = ref<number | null>(null)
const dragOver = ref<number | null>(null)

function onDragStart(i: number) {
  dragIndex.value = i
}
function onDrop(target: number) {
  if (dragIndex.value === null || dragIndex.value === target) return
  emit('reorder', dragIndex.value, target)
  dragIndex.value = null
  dragOver.value = null
}

const themeTag = computed(() => {
  const count = props.day.attractions.length
  if (count === 0) return '休整日'
  const tags: Record<number, string> = {
    1: '城市核心',
    2: '探索之旅',
    3: '深度漫游',
    4: '满载日程',
  }
  return tags[count] || '充实日程'
})
</script>

<template>
  <section class="day glass" :id="`day-${day.index}`">
    <header class="day-head">
      <span class="index">{{ day.index }}</span>
      <div class="head-text">
        <p class="date">{{ day.date }}</p>
        <p class="theme">{{ themeTag }}</p>
      </div>
      <div v-if="day.weather" class="weather">
        <span class="w-main">{{ day.weather.day_desc || '—' }}</span>
        <span v-if="day.weather.temp_min != null && day.weather.temp_max != null" class="w-temp">
          {{ day.weather.temp_min }}° / {{ day.weather.temp_max }}°
        </span>
      </div>
    </header>

    <div class="attractions">
      <div
        v-for="(a, i) in day.attractions"
        :key="i"
        class="attr-row"
        :class="{ 'drag-over': dragOver === i, draggable: editable }"
        :draggable="editable"
        @dragstart="onDragStart(i)"
        @dragover.prevent="dragOver = i"
        @drop="onDrop(i)"
        @dragend="dragOver = null"
      >
        <span v-if="editable" class="seq">{{ i + 1 }}</span>
        <AttractionCard :attraction="a" />
        <button v-if="editable" class="remove" title="移除景点" @click="emit('remove-attraction', i)">✕</button>
      </div>
      <p v-if="day.attractions.length === 0" class="empty">这天留给你自由探索 ✨</p>
    </div>

    <div v-if="day.hotel" class="hotel">
      <span class="h-label">入住</span>
      <span class="h-name">{{ day.hotel.name }}</span>
      <span v-if="day.hotel.price_per_night != null" class="h-price">¥{{ day.hotel.price_per_night }}/晚</span>
      <span v-if="day.hotel.star" class="h-star">{{ '★'.repeat(Math.min(day.hotel.star, 5)) }}</span>
    </div>
  </section>
</template>

<style scoped>
.day {
  border-radius: var(--radius-lg);
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  scroll-margin-top: 100px;
  background: var(--glass);
  backdrop-filter: blur(20px) saturate(1.4);
  -webkit-backdrop-filter: blur(20px) saturate(1.4);
  border: 1px solid var(--glass-border);
  box-shadow: var(--shadow-1);
}
.day-head {
  display: flex;
  align-items: center;
  gap: 16px;
  padding-bottom: 14px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
.index {
  width: 44px;
  height: 44px;
  flex-shrink: 0;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--accent) 0%, var(--accent-2) 100%);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: 700;
  box-shadow: 0 4px 12px rgba(10, 132, 255, 0.35);
}
.head-text { flex: 1; }
.date { margin: 0; font-size: 14px; font-weight: 600; color: var(--text); }
.theme { margin: 2px 0 0; font-size: 12px; color: var(--muted); }
.weather {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
}
.w-main { font-size: 13px; color: var(--text-2); }
.w-temp { font-size: 13px; color: var(--accent-4); font-weight: 600; }

.attractions { display: flex; flex-direction: column; gap: 10px; }
.attr-row {
  display: flex;
  align-items: stretch;
  gap: 8px;
}
.attr-row.draggable { cursor: grab; }
.attr-row.drag-over { opacity: 0.6; outline: 2px dashed var(--accent); border-radius: var(--radius); }
.seq {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  font-size: 11px;
  color: var(--muted);
  font-weight: 700;
}
.remove {
  background: transparent;
  border: none;
  color: var(--error);
  cursor: pointer;
  font-size: 14px;
  padding: 0 6px;
  opacity: 0.5;
  transition: opacity 0.18s;
}
.remove:hover { opacity: 1; }
.empty {
  margin: 0;
  padding: 20px;
  text-align: center;
  color: var(--muted);
  font-size: 14px;
}

.hotel {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  border-radius: var(--radius);
  background: linear-gradient(135deg, rgba(191, 90, 242, 0.10), rgba(10, 132, 255, 0.08));
  border: 1px solid rgba(191, 90, 242, 0.18);
  font-size: 13.5px;
}
.h-label { color: var(--muted); font-size: 12px; }
.h-name { font-weight: 600; color: var(--text); flex: 1; }
.h-price {
  font-size: 13px;
  font-weight: 600;
  color: var(--accent-3);
}
.h-star { color: var(--warn); font-size: 12px; letter-spacing: 1px; }
</style>