import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { Composer } from './Composer'

function setup(disabled = false) {
  const onSend = vi.fn()
  render(<Composer placeholder="Ask something" disabled={disabled} onSend={onSend} onAttach={() => {}} />)
  return { onSend, box: screen.getByRole('textbox', { name: 'Your question' }) }
}

describe('<Composer>', () => {
  it('sends the trimmed question on Enter and clears the box', async () => {
    const { onSend, box } = setup()

    await userEvent.type(box, '  What is the refund policy?  {Enter}')

    expect(onSend).toHaveBeenCalledWith('What is the refund policy?')
    expect(box).toHaveValue('')
  })

  it('adds a new line on Shift+Enter instead of sending', async () => {
    const { onSend, box } = setup()

    await userEvent.type(box, 'line one{Shift>}{Enter}{/Shift}line two')

    expect(onSend).not.toHaveBeenCalled()
    expect(box).toHaveValue('line one\nline two')
  })

  it('does not send an empty question', async () => {
    const { onSend, box } = setup()

    await userEvent.type(box, '   {Enter}')

    expect(onSend).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: 'Send' })).toBeDisabled()
  })

  it('does not send while an answer is still coming', async () => {
    const { onSend, box } = setup(true)

    await userEvent.type(box, 'Another question{Enter}')

    expect(onSend).not.toHaveBeenCalled()
  })
})
