import api from './index'

export const getCarriers = () => api.get('/logistics/carriers')
export const getShipments = (params) => api.get('/logistics', { params })
export const getShipmentDetail = (orderId) => api.get('/logistics/' + orderId)
export const addShipment = (orderId, data) => api.post('/logistics/' + orderId + '/add', data)
export const updateShipment = (shipmentId, data) => api.put('/logistics/shipment/' + shipmentId + '/ship', data)
export const deleteShipment = (shipmentId) => api.delete('/logistics/shipment/' + shipmentId)
export const refreshShipment = (shipmentId) => api.post('/logistics/shipment/' + shipmentId + '/refresh')
export const updateSN = (shipmentId, data) => api.post('/logistics/shipment/' + shipmentId + '/update-sn', data)
export const shipOrder = (orderId, data) => api.post('/logistics/' + orderId + '/ship', data)
export const getPendingOrders = () => api.get('/logistics/pending-orders')
