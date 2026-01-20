import { useEffect } from 'react'

export function useHotkey(
  key: string,
  callback: () => void,
  dependencies: any[] = []
) {
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      // Don't trigger if user is typing in an input field
      const target = event.target as HTMLElement
      if (
        target.tagName === 'INPUT' ||
        target.tagName === 'TEXTAREA' ||
        target.contentEditable === 'true'
      ) {
        return
      }

      // Check if the pressed key matches our hotkey
      if (event.key === key || event.code === key) {
        event.preventDefault()
        callback()
      }
    }

    window.addEventListener('keydown', handleKeyDown)

    return () => {
      window.removeEventListener('keydown', handleKeyDown)
    }
  }, [key, callback, ...dependencies])
}