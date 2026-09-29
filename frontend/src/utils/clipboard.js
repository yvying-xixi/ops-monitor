/** 剪贴板工具：优先 Clipboard API，失败或非安全上下文时降级 execCommand。 */

export async function copyText(text) {
  const value = text == null ? '' : String(text)
  if (!value) return false

  if (navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(value)
      return true
    } catch {
      // 继续走 execCommand 降级
    }
  }

  try {
    const textarea = document.createElement('textarea')
    textarea.value = value
    textarea.setAttribute('readonly', '')
    textarea.style.position = 'fixed'
    textarea.style.top = '0'
    textarea.style.left = '-9999px'
    document.body.appendChild(textarea)

    const selection = document.getSelection()
    const previousRange = selection && selection.rangeCount > 0 ? selection.getRangeAt(0) : null

    textarea.select()
    textarea.setSelectionRange(0, value.length)
    const ok = document.execCommand('copy')
    document.body.removeChild(textarea)

    if (selection && previousRange) {
      selection.removeAllRanges()
      selection.addRange(previousRange)
    }
    return ok
  } catch {
    return false
  }
}
