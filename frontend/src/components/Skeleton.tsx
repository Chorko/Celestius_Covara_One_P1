interface SkeletonProps {
  width?: string
  height?: string
  className?: string
  variant?: 'block' | 'text' | 'circle'
  lines?: number
}

/**
 * Reusable skeleton shimmer placeholder for loading states.
 * Uses the .skeleton CSS class from globals.css.
 */
export default function Skeleton({
  width = '100%',
  height = '1rem',
  className = '',
  variant = 'block',
  lines = 1,
}: SkeletonProps) {
  if (variant === 'circle') {
    return (
      <div
        className={`skeleton ${className}`}
        style={{ width: height, height, borderRadius: '50%' }}
      />
    )
  }

  if (variant === 'text' && lines > 1) {
    return (
      <div className={`space-y-2 ${className}`}>
        {Array.from({ length: lines }).map((_, i) => (
          <div
            key={i}
            className="skeleton"
            style={{
              width: i === lines - 1 ? '60%' : width,
              height,
            }}
          />
        ))}
      </div>
    )
  }

  return (
    <div
      className={`skeleton ${className}`}
      style={{ width, height }}
    />
  )
}
