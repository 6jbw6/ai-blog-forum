import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAiChatStore = defineStore('aiChat', () => {
  const isChatOpen = ref(false)
  const isSearchOpen = ref(false)
  const pendingQuestion = ref('')

  function openChat(question?: string) {
    if (question) {
      pendingQuestion.value = question
    }
    isChatOpen.value = true
  }

  function closeChat() {
    isChatOpen.value = false
  }

  function openSearch() {
    isSearchOpen.value = true
  }

  function closeSearch() {
    isSearchOpen.value = false
  }

  return {
    isChatOpen,
    isSearchOpen,
    pendingQuestion,
    openChat,
    closeChat,
    openSearch,
    closeSearch
  }
})
