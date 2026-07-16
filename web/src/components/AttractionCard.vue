<script setup lang="ts">
import type { Attraction } from '../types'

defineProps<{ attraction: Attraction }>()
</script>

<template>
  <div class="card">
    <img v-if="attraction.image_url" :src="attraction.image_url" :alt="attraction.name" />
    <div v-else class="img-placeholder">无图</div>
    <div class="body">
      <div class="head">
        <span class="name">{{ attraction.name }}</span>
        <span v-if="attraction.rating" class="rating">★ {{ attraction.rating }}</span>
      </div>
      <p v-if="attraction.address" class="addr">{{ attraction.address }}</p>
      <p v-if="attraction.ticket_price != null" class="price">
        门票 {{ attraction.ticket_price }} 元
      </p>
    </div>
  </div>
</template>

<style scoped>
.card { display: flex; gap: 10px; background: var(--panel); border-radius: 10px; overflow: hidden; }
img, .img-placeholder { width: 96px; height: 72px; object-fit: cover; flex-shrink: 0; background: var(--bubble); display: flex; align-items: center; justify-content: center; color: var(--muted); font-size: 12px; }
.body { padding: 8px 10px; display: flex; flex-direction: column; gap: 4px; }
.head { display: flex; align-items: center; gap: 8px; }
.name { font-weight: 600; }
.rating { color: var(--warn); font-size: 12px; }
.addr { margin: 0; font-size: 12px; color: var(--muted); }
.price { margin: 0; font-size: 12px; color: var(--ok); }
</style>