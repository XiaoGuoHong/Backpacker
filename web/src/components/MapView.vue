<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import AMapLoader from '@amap/amap-jsapi-loader'
import type { ItineraryDay } from '../types'

const props = defineProps<{ days: ItineraryDay[]; amapJsKey: string | null }>()

const container = ref<HTMLDivElement | null>(null)
const error = ref('')
const disabled = ref(false)
const loading = ref(true)
let map: any = null
let markers: any[] = []
let polylines: any[] = []

type Point = { lng: number; lat: number; name: string; day: number }

function collectPoints(): { points: Point[]; byDay: Point[][] } {
  const points: Point[] = []
  const byDay: Point[][] = []
  props.days.forEach((d) => {
    const dayPts: Point[] = []
    d.attractions.forEach((a) => {
      if (a.location && a.location.lng != null && a.location.lat != null) {
        const p = { lng: a.location.lng, lat: a.location.lat, name: a.name, day: d.index }
        points.push(p)
        dayPts.push(p)
      }
    })
    if (d.hotel && d.hotel.location && d.hotel.location.lng != null && d.hotel.location.lat != null) {
      const p = { lng: d.hotel.location.lng, lat: d.hotel.location.lat, name: d.hotel.name, day: d.index }
      points.push(p)
      dayPts.push(p)
    }
    byDay.push(dayPts)
  })
  return { points, byDay }
}

async function render() {
  if (!map || !container.value) return
  markers.forEach((m) => map.remove(m))
  polylines.forEach((p) => map.remove(p))
  markers = []
  polylines = []
  const { points, byDay } = collectPoints()
  if (points.length === 0) {
    error.value = '暂无可标注的坐标数据'
    return
  }
  error.value = ''
  const AMap = (window as any).AMap
  const colors = ['#0a84ff', '#bf5af2', '#30d158', '#ff9f0a', '#ff375f']
  points.forEach((p) => {
    const color = colors[(p.day - 1) % colors.length]
    const marker = new AMap.Marker({
      position: [p.lng, p.lat],
      title: p.name,
      label: { content: `<div style="background:${color};color:#fff;padding:2px 6px;border-radius:6px;font-size:11px;">Day${p.day} ${p.name}</div>`, direction: 'top' },
    })
    map.add(marker)
    markers.push(marker)
  })
  byDay.forEach((dayPts, idx) => {
    if (dayPts.length >= 2) {
      const path = dayPts.map((p) => [p.lng, p.lat])
      const polyline = new AMap.Polyline({
        path,
        strokeColor: colors[idx % colors.length],
        strokeWeight: 3,
        strokeOpacity: 0.85,
      })
      map.add(polyline)
      polylines.push(polyline)
    }
  })
  map.setFitView(markers, false)
}

async function init() {
  if (!props.amapJsKey) {
    disabled.value = true
    loading.value = false
    return
  }
  try {
    const AMap = await AMapLoader.load({ key: props.amapJsKey, version: '2.0', plugins: [] })
    map = new AMap.Map(container.value, { zoom: 11, viewMode: '2D' })
    await render()
    loading.value = false
  } catch (e) {
    disabled.value = true
    loading.value = false
    error.value = e instanceof Error ? e.message : '地图加载失败'
  }
}

watch(
  () => props.days,
  () => {
    if (map) render()
  },
  { deep: true },
)

onBeforeUnmount(() => {
  if (map) {
    map.destroy()
    map = null
  }
})

init()
</script>

<template>
  <section class="map glass">
    <div class="head">
      <span class="dot" />
      <h3>地图</h3>
    </div>
    <div v-if="disabled" class="fallback">
      <p class="muted">未配置高德 JS Key，已降级为坐标列表。</p>
      <ul>
        <li v-for="d in days" :key="d.index">
          <span class="day-label">Day {{ d.index }}</span>
          <span v-for="(a, i) in d.attractions" :key="i" class="item">
            《{{ a.name }}》
            <span v-if="a.location?.lng != null" class="coord">
              ({{ a.location.lng?.toFixed(4) }}, {{ a.location.lat?.toFixed(4) }})
            </span>
          </span>
          <span v-if="d.hotel?.location?.lng != null" class="item">
            酒店：{{ d.hotel.name }}
          </span>
        </li>
      </ul>
    </div>
    <div v-else class="map-canvas-wrap">
      <div v-if="loading" class="loading">加载地图中…</div>
      <div ref="container" class="map-canvas" />
      <p v-if="error" class="muted">{{ error }}</p>
    </div>
  </section>
</template>

<style scoped>
.map {
  border-radius: var(--radius-lg);
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  background: var(--glass);
  backdrop-filter: blur(20px) saturate(1.4);
  -webkit-backdrop-filter: blur(20px) saturate(1.4);
  border: 1px solid var(--glass-border);
  box-shadow: var(--shadow-1);
  min-height: 280px;
}
.head { display: flex; align-items: center; gap: 8px; }
.dot {
  width: 8px; height: 8px;
  border-radius: 50%;
  background: var(--accent);
}
h3 { margin: 0; font-size: 15px; font-weight: 600; }
.map-canvas-wrap { position: relative; }
.map-canvas {
  width: 100%;
  height: 320px;
  border-radius: var(--radius);
  overflow: hidden;
}
.loading {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--muted);
  font-size: 13px;
  z-index: 2;
}
.fallback ul {
  margin: 8px 0 0;
  padding-left: 18px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
  color: var(--text-2);
}
.day-label { color: var(--accent); font-weight: 600; margin-right: 6px; }
.item { font-size: 13px; margin-right: 10px; }
.coord { color: var(--muted); font-size: 12px; }
.muted { color: var(--muted); font-size: 13px; margin: 8px 0 0; }
</style>