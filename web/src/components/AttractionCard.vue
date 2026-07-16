<script setup lang="ts">
import type { Attraction } from '../types'

defineProps<{ attraction: Attraction }>()
</script>

<template>
  <article class="card">
    <div class="media">
      <img v-if="attraction.image_url" :src="attraction.image_url" :alt="attraction.name" loading="lazy" />
      <div v-else class="placeholder">
        <span>{{ attraction.name?.slice(0, 1) || '景' }}</span>
      </div>
    </div>
    <div class="body">
      <div class="head">
        <h4 class="name">{{ attraction.name }}</h4>
        <span v-if="attraction.rating" class="rating">
          <span class="star">★</span>{{ attraction.rating.toFixed(1) }}
        </span>
      </div>
      <p v-if="attraction.address" class="addr">{{ attraction.address }}</p>
      <div class="meta">
        <span v-if="attraction.ticket_price != null && attraction.ticket_price > 0" class="price">
          门票 ¥{{ attraction.ticket_price }}
        </span>
        <span v-else class="price free">免费</span>
      </div>
    </div>
  </article>
</template>

<style scoped>
.card {
  display: flex;
  gap: 14px;
  padding: 12px;
  border-radius: var(--radius);
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--glass-border);
  transition: all 0.18s ease;
  overflow: hidden;
}
.card:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.16);
  transform: translateY(-1px);
}
.media {
  width: 96px;
  height: 96px;
  flex-shrink: 0;
  border-radius: 14px;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.06);
}
.media img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: 32px;
  font-weight: 700;
}
.body { display: flex; flex-direction: column; gap: 5px; flex: 1; min-width: 0; }
.head { display: flex; align-items: center; gap: 10px; }
.name {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.rating {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  font-size: 12.5px;
  color: var(--warn);
  font-weight: 600;
}
.star { font-size: 11px; }
.addr {
  margin: 0;
  font-size: 12.5px;
  color: var(--muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.meta { margin-top: 4px; }
.price {
  display: inline-block;
  font-size: 12px;
  padding: 2px 8px;
  border-radius: var(--radius-pill);
  background: rgba(10, 132, 255, 0.16);
  color: #66c4ff;
  font-weight: 600;
}
.price.free {
  background: rgba(48, 209, 88, 0.15);
  color: var(--ok);
}
</style>