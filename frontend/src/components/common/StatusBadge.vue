<template>
  <span :class="badgeClass">{{ displayLabel }}</span>
</template>

<script setup>
import { computed } from 'vue'
import {
  orderTypeBadges, orderTypeNames,
  logTypeBadges, logTypeNames,
  purchaseStatusBadges, purchaseStatusNames,
  shipmentStatusBadges, shipmentStatusNames,
  shippingStatusBadges, shippingStatusNames,
  dropshipStatusBadges, dropshipStatusNames
} from '../../utils/constants'

const props = defineProps({
  type: {
    type: String,
    required: true
    // 'orderType' | 'logType' | 'purchaseStatus' | 'shippingStatus'
  },
  status: {
    type: String,
    required: true
  },
  label: {
    type: String,
    default: ''
  }
})

const badgeMap = {
  orderType: orderTypeBadges,
  logType: logTypeBadges,
  purchaseStatus: purchaseStatusBadges,
  shipmentStatus: shipmentStatusBadges,
  shippingStatus: shippingStatusBadges,
  dropshipStatus: dropshipStatusBadges
}

const nameMap = {
  orderType: orderTypeNames,
  logType: logTypeNames,
  purchaseStatus: purchaseStatusNames,
  shipmentStatus: shipmentStatusNames,
  shippingStatus: shippingStatusNames,
  dropshipStatus: dropshipStatusNames
}

const badgeClass = computed(() => badgeMap[props.type]?.[props.status] || 'badge badge-gray')
const displayLabel = computed(() => props.label || nameMap[props.type]?.[props.status] || props.status)
</script>
