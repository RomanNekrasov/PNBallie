<template>
  <div class="bg-white/5 rounded-lg px-3 py-2">
    <div class="text-[11px] text-white/40 uppercase tracking-wide">{{ label }}</div>
    <div class="text-sm font-medium">{{ value }}</div>
    <div v-if="sub" class="text-[11px] text-white/30">{{ sub }}</div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  label: string
  value: string
  sub?: string
}>()
</script>
