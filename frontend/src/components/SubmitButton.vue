<template>
  <button
    @click="$emit('submit')"
    :disabled="disabled"
    class="px-6 py-3 rounded-xl font-bold text-white shadow-lg transition-all active:scale-95"
    :class="disabled ? 'bg-white/10 opacity-40 cursor-not-allowed' : 'bg-emerald-600 active:bg-emerald-700'"
  >
    <span v-if="submitting">Opslaan...</span>
    <span v-else>Opslaan</span>
  </button>
</template>

<script setup lang="ts">
defineProps<{
  disabled: boolean
  submitting: boolean
}>()

defineEmits<{
  submit: []
}>()
</script>
