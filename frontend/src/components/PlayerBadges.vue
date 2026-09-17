<template>
  <div class="profile-badges" aria-label="Verdiende badges">
    <p v-if="!badges.length" class="badges-empty">Nog geen badges. De eerste overwinning levert de eerste badge op.</p>
    <div v-for="badge in badges" :key="badge.key" class="profile-badge">
      <GameIcon :asset="badge.key" :fallback="badge.emoji" :size="56" />
      <div class="badge-copy">
        <strong>{{ badge.label }}</strong>
        <span>{{ badge.description }}</span>
        <time :datetime="badge.earned_at">Verdiend op {{ earnedDate(badge.earned_at) }}</time>
      </div>
      <BadgeHelp :label="badge.label" :description="`${badge.description} Deze badge blijft verdiend, ook na een verliespartij. Statistiekfilters veranderen dit niet.`" />
    </div>
  </div>
</template>

<script setup lang="ts">
import type { PlayerBadge } from '../types'
import { parseUtcTimestamp } from '../dateTime'
import GameIcon from './GameIcon.vue'
import BadgeHelp from './BadgeHelp.vue'

defineProps<{ badges: PlayerBadge[] }>()

function earnedDate(value: string): string {
  return parseUtcTimestamp(value).toLocaleDateString('nl-NL', { day: 'numeric', month: 'short', year: 'numeric' })
}
</script>

<style scoped>
.profile-badges { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(240px, 100%), 1fr)); gap: 10px; }
.profile-badge { display: flex; align-items: center; gap: 12px; padding: 12px; border: 1px solid #5b4e34; border-radius: 12px; background: #2b261c; }
.badge-copy { display: grid; gap: 4px; min-width: 0; }
.profile-badge strong { color: #ffd287; font-size: 14px; }
.profile-badge span, .profile-badge time, .badges-empty { color: #aeb8c5; font-size: 11px; line-height: 1.5; }
.profile-badge time { font-size: 10px; }
</style>
