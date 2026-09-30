/**
 * Error state with retry option.
 */
interface Props {
  message: string | null
  onRetry?: () => void
}

export default function ErrorState({ message, onRetry }: Props) {
  return (
    <div className="flex flex-col items-center justify-center py-16 space-y-4">
      <span className="text-3xl">⚠️</span>
      <p className="text-sm text-text-muted text-center max-w-md">
        {message || 'Si è verificato un errore. Riprova più tardi.'}
      </p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="px-4 py-2 bg-brand text-white text-sm rounded-lg hover:bg-brand-dark transition-colors"
        >
          Riprova
        </button>
      )}
    </div>
  )
}
