<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import AMapLoader from '@amap/amap-jsapi-loader'
import type { ItineraryDay } from '../types'

const props = defineProps<{ days: ItineraryDay[]; amapJsKey: string | null }>()

const container = ref<HTMLDivElement | null>(null)
const error = ref('')
const disabled = ref(false)
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
  points.forEach((p) => {
    const marker = new AMap.Marker({
      position: [p.lng, p.lat],
      title: p.name,
      label: { content: `Day${p.day} ${p.name}`, direction: 'top' },
    })
    map.add(marker)
    markers.push(marker)
  })
  byDay.forEach((dayPts) => {
    if (dayPts.length >= 2) {
      const path = dayPts.map((p) => [p.lng, p.lat])
      const polyline = new AMap.Polyline({ path, strokeColor: '#2563eb', strokeWeight: 3, strokeOpacity: 0.8 })
      map.add(polyline)
      polylines.push(polyline)
    }
  })
  map.setFitView(markers, false)
}

async function init() {
  if (!props.amapJsKey) {
    disabled.value = true
    return
  }
  try {
    const AMap = await AMapLoader.load({ key: props.amapJsKey, version: '2.0', plugins: [] })
    map = new AMap.Map(container.value, { zoom: 11, viewMode: '2D' })
    await render()
  } catch (e) {
    disabled.value = true
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
  <section class="map-view">
    <h3>地图</h3>
    <div v-if="disabled" class="fallback">
      <p class="muted">未配置高德 JS Key，地图已降级。景点坐标列表：</p>
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
            ({{ d.hotel.location.lng?.toFixed(4) }}, {{ d.hotel.location.lat?.toFixed(4) }})
          </span>
        </li>
      </ul>
    </div>
    <div v-else ref="container" class="map-canvas" />
    <p v-if="!disabled && error" class="muted">{{ error }}</p>
  </section>
</template>

<style scoped>
.map-view { background: var(--panel); border-radius: 12px; padding: 16px; display: flex; flex-direction: column; gap: 8px; }
h3 { margin: 0; }
.map-canvas { width: 100%; height: 360px; border-radius: 8px; overflow: hidden; }
.fallback ul { margin: 8px 0 0; padding-left: 18px; display: flex; flex-direction: column; gap: 6px; }
.day-label { color: var(--user); font-weight: 600; margin-right: 6px; }
.item { font-size: 13px; margin-right: 8px; }
.coord { color: var(--muted); font-size: 12px; }
.muted { color: var(--muted); font-size: 13px; margin: 0; }
</style>