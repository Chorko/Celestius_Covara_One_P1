"use client"

interface SkeletonProps {
  width?: string
  height?: string
  className?: string
}

export default function Skeleton({
  width = '100%',
  height = '1rem',
  className = '',
}: SkeletonProps) {
  return (
    <div
      className={`skeleton ${className}`}
      style={{ width, height, minHeight: height }}
      aria-hidden="true"
    />
  )
}
