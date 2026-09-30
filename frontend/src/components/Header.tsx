import { LogoMark } from './icons'

export type Step = 'input' | 'results'

export default function Header({
  step,
  canOpenResults,
  onGoInput,
  onGoResults,
}: {
  step: Step
  canOpenResults: boolean
  onGoInput: () => void
  onGoResults: () => void
}) {
  const item = (n: number, label: string, active: boolean, onClick?: () => void) => {
    const inner = (
      <>
        <span
          className={`grid size-7 place-items-center rounded-full text-sm font-bold tabular ${
            active ? 'bg-forest text-white' : 'border border-field text-ink-soft'
          }`}
        >
          {n}
        </span>
        <span className={active ? 'font-semibold text-ink' : 'text-ink-soft'}>{label}</span>
      </>
    )
    const cls = 'flex items-center gap-2 rounded-lg px-1.5 py-1 text-[0.95rem]'
    return onClick && !active ? (
      <button type="button" onClick={onClick} className={`${cls} hover:bg-paper-deep`}>
        {inner}
      </button>
    ) : (
      <span className={cls} aria-current={active ? 'step' : undefined}>
        {inner}
      </span>
    )
  }

  return (
    <header className="border-b border-line/80">
      <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-x-6 gap-y-3 px-4 py-4 sm:px-6">
        <a href="/" className="flex items-center gap-2.5 rounded-lg" aria-label="BestBill, pagina iniziale">
          <LogoMark size={34} />
          <span className="font-display text-2xl font-semibold tracking-tight">BestBill</span>
        </a>
        <nav aria-label="Passi" className="flex items-center gap-1 sm:gap-3">
          {item(1, 'I tuoi consumi', step === 'input', onGoInput)}
          <span aria-hidden="true" className="h-px w-6 bg-field sm:w-10" />
          {item(2, 'Le offerte', step === 'results', canOpenResults ? onGoResults : undefined)}
        </nav>
      </div>
    </header>
  )
}
