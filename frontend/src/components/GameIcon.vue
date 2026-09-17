<template>
  <span
    class="game-icon"
    :style="{ width: `${size}px`, height: `${size}px`, fontSize: `${size}px` }"
    :data-asset="asset"
    :role="label ? 'img' : undefined"
    :aria-label="label || undefined"
    :aria-hidden="label ? undefined : true"
  >
    <img v-if="src && src !== failedSrc" :src="src" alt="" draggable="false" @error="failedSrc = src" />
    <span v-else class="game-icon-fallback">{{ fallback }}</span>
  </span>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { gameAssetUrl } from '../gameAssets'

const props = withDefaults(defineProps<{
  asset: string
  size?: number
  label?: string
  fallback?: string
}>(), { size: 48, label: '', fallback: '◆' })

const src = computed(() => gameAssetUrl(props.asset))
const failedSrc = ref<string>()
</script>

<style scoped>
.game-icon { display: inline-flex; flex: 0 0 auto; align-items: center; justify-content: center; vertical-align: middle; }
.game-icon img { display: block; width: 100%; height: 100%; object-fit: contain; }
.game-icon-fallback { font-size: 0.65em; line-height: 1; }
</style>
