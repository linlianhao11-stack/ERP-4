import { ref } from 'vue'

const KEY_PREFIX = 'ai_favorites_'
const MAX_FAVORITES = 20

export function useAiFavorites(userId) {
  const favorites = ref([])

  const load = () => {
    try {
      const raw = localStorage.getItem(`${KEY_PREFIX}${userId}`)
      favorites.value = raw ? JSON.parse(raw) : []
    } catch { favorites.value = [] }
  }

  const save = () => {
    localStorage.setItem(`${KEY_PREFIX}${userId}`, JSON.stringify(favorites.value))
  }

  const addFavorite = (question) => {
    const idx = favorites.value.findIndex(f => f.question === question)
    if (idx >= 0) {
      favorites.value[idx].timestamp = Date.now()
    } else {
      favorites.value.unshift({ question, timestamp: Date.now() })
      if (favorites.value.length > MAX_FAVORITES) favorites.value.pop()
    }
    save()
  }

  const removeFavorite = (index) => {
    favorites.value.splice(index, 1)
    save()
  }

  const isFavorited = (question) => favorites.value.some(f => f.question === question)

  load()

  return { favorites, addFavorite, removeFavorite, isFavorited }
}
