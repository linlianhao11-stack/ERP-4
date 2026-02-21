<template>
  <teleport to="body">
    <div v-if="visible" class="modal-overlay" @click.self="onOverlayClick">
      <div class="modal-content" :style="widthStyle" @click.stop>
        <div class="modal-header">
          <h3 class="modal-title">{{ title }}</h3>
          <button v-if="closable" @click="$emit('close')" class="modal-close">&times;</button>
        </div>
        <div class="modal-body">
          <slot />
        </div>
        <div v-if="$slots.footer" class="px-6 pb-5">
          <slot name="footer" />
        </div>
      </div>
    </div>
  </teleport>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  title: {
    type: String,
    default: ''
  },
  width: {
    type: String,
    default: '800px'
  },
  closable: {
    type: Boolean,
    default: true
  },
  closeOnOverlay: {
    type: Boolean,
    default: true
  }
})

const emit = defineEmits(['close'])

const widthStyle = computed(() => ({
  maxWidth: props.width
}))

function onOverlayClick() {
  if (props.closeOnOverlay) {
    emit('close')
  }
}
</script>
