import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { Source } from '../lib/types'
import { Answer, citedNumbers, linkCitations } from './Answer'

describe('linkCitations', () => {
  it('turns [2] and [1, 3] into citation links', () => {
    expect(linkCitations('See [2] and [1, 3].')).toBe('See [2](#cite-2) and [1](#cite-1)[3](#cite-3).')
  })

  it('leaves real markdown links alone', () => {
    expect(linkCitations('[docs](https://example.com)')).toBe('[docs](https://example.com)')
  })
})

describe('citedNumbers', () => {
  it('lists each cited passage once, in order of first mention', () => {
    expect(citedNumbers('A [3]. B [1, 3]. C [2].')).toEqual([3, 1, 2])
  })
})

const sources: Source[] = [
  { document_id: 'doc-1', text: 'Refunds take 30 days.' },
  { document_id: 'doc-1', text: 'Shipping is free over $50.' },
  { document_id: 'doc-2', text: 'Support is open on weekdays.' },
]

describe('<Answer>', () => {
  it('shows only the passages the answer cites, with a way to show the rest', async () => {
    render(<Answer uid="a" content="Refunds take a month [1]." sources={sources} />)

    expect(screen.getByText('Refunds take 30 days.')).toBeInTheDocument()
    expect(screen.queryByText('Shipping is free over $50.')).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Show all 3 passages' }))
    expect(screen.getByText('Shipping is free over $50.')).toBeInTheDocument()
    expect(screen.getByText('Support is open on weekdays.')).toBeInTheDocument()
  })

  it('opens the cited passage in the document preview', async () => {
    const onOpenSource = vi.fn()
    render(<Answer uid="a" content="Shipping is free [2]." sources={sources} onOpenSource={onOpenSource} />)

    await userEvent.click(screen.getByRole('button', { name: 'Show source 2' }))

    expect(onOpenSource).toHaveBeenCalledWith(sources[1])
  })

  it('ignores a citation to a passage that does not exist', () => {
    render(<Answer uid="a" content="Made up [9]." sources={sources} />)
    expect(screen.queryByRole('button', { name: 'Show source 9' })).not.toBeInTheDocument()
  })

  it('hides the copy button and passage toggle while still streaming', () => {
    render(<Answer uid="a" content="Refunds [1]" sources={sources} streaming />)
    expect(screen.queryByRole('button', { name: /copy/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /show all/i })).not.toBeInTheDocument()
  })

  it('marks answers that came from the cache', () => {
    render(<Answer uid="a" content="Refunds [1]." sources={sources} cached />)
    expect(screen.getByText('Instant (cached)')).toBeInTheDocument()
  })
})
