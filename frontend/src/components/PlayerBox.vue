<template>
  <button
    @click="$emit('tap')"
    class="w-[90px] h-[90px] rounded-xl text-white font-semibold text-sm leading-tight flex flex-col items-center justify-center active:scale-95 transition-transform"
    :style="glassStyle"
  >
    <span class="text-[10px] uppercase tracking-wider opacity-75">{{ label }}</span>
    <span class="truncate max-w-[90px]">{{ playerName || 'Kies...' }}</span>
  </button>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  team: 'orange' | 'blue'
  label: string
  playerName: string | null
}>()

defineEmits<{
  tap: []
}>()

const glassStyle = computed(() => {
  const color = props.team === 'orange' ? '217, 124, 46' : '45, 95, 161'
  return {
    background: `rgba(${color}, 0.45)`,
    backdropFilter: 'blur(16px) saturate(180%)',
    WebkitBackdropFilter: 'blur(16px) saturate(180%)',
    border: `1px solid rgba(${color}, 0.65)`,
    boxShadow: `0 4px 24px rgba(0,0,0,0.25), inset 0 1px 0 rgba(255,255,255,0.2)`,
  }
})
</script>
