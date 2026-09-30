/**
 * Loading state with animated spinner.
 */
interface Props {
  message: string
}

export default function LoadingState({ message }: Props) {
  return (
    <div className="flex flex-col items-center justify-center py-16 space-y-4">
      <div className="w-8 h-8 border-4 border-brand/30 border-t-brand rounded-full animate-spin" />
      <p className="text-sm text-text-muted text-center">{message}</p>
    </div>
  )
}
