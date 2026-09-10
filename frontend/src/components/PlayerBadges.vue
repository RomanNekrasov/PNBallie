<template>
  <div class="profile-badges" aria-label="Verdiende badges">
    <p v-if="!badges.length" class="badges-empty">Nog geen badges. De eerste overwinning levert de eerste badge op.</p>
    <div v-for="badge in badges" :key="badge.key" class="profile-badge" :title="badge.description">
      <span class="badge-emoji" aria-hidden="true">{{ badge.emoji }}</span>
      <div>
        <strong>{{ badge.label }}</strong>
        <span>{{ badge.description }}</span>
        <time :datetime="badge.earned_at">Verdiend op {{ earnedDate(badge.earned_at) }}</time>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { PlayerBadge } from '../types'
import { parseUtcTimestamp } from '../dateTime'

defineProps<{ badges: PlayerBadge[] }>()

function earnedDate(value: string): string {
  return parseUtcTimestamp(value).toLocaleDateString('nl-NL', { day: 'numeric', month: 'short', year: 'numeric' })
}
</script>

<style scoped>
.profile-badges { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(240px, 100%), 1fr)); gap: 10px; }
.profile-badge { display: flex; align-items: center; gap: 12px; padding: 12px; border: 1px solid #5b4e34; border-radius: 12px; background: #2b261c; }
.badge-emoji { font-size: 26px; }
.profile-badge > div { display: grid; gap: 4px; }
.profile-badge strong { color: #ffd287; font-size: 14px; }
.profile-badge span, .profile-badge time, .badges-empty { color: #aeb8c5; font-size: 11px; line-height: 1.5; }
.profile-badge time { font-size: 10px; }
</style>
