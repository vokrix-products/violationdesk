import { Clock, CircleCheckBig, TriangleAlert } from 'lucide-react'

export const labels = [
  {
    value: 'bug',
    label: 'Bug',
  },
  {
    value: 'feature',
    label: 'Feature',
  },
  {
    value: 'documentation',
    label: 'Documentation',
  },
]

// Severity tiers drive badge color. Every status maps to exactly one tier:
//   critical -> red (destructive)   e.g. expired, denied, failed
//   warning  -> amber (warning)     e.g. expiring soon, needs review
//   good     -> green (success)     e.g. valid, approved, done
//   neutral  -> gray (secondary)    e.g. pending, queued, n/a
export type Severity = 'critical' | 'warning' | 'good' | 'neutral'

export const severityToBadgeVariant: Record<Severity, 'destructive' | 'warning' | 'success' | 'secondary'> = {
  critical: 'destructive',
  warning: 'warning',
  good: 'success',
  neutral: 'secondary',
}

// PRODUCT_CUSTOMIZE: replace this list with the real statuses this product
// produces (must match exactly what the backend poller writes to
// records.status). Every status must declare a severity tier above. Default
// values below are generic placeholders only — do not ship as-is.
// __STATUSES_BLOCK_START__
export const statuses: {
  label: string
  value: string
  icon: typeof TriangleAlert
  severity: Severity
}[] = [
  { label: 'New', value: 'New:info', icon: Clock, severity: 'info' as Severity },
  { label: 'Missing', value: 'Missing:warning', icon: Clock, severity: 'warning' as Severity },
  { label: 'Valid', value: 'Valid:good', icon: CircleCheckBig, severity: 'good' as Severity },
  { label: 'Notice Sent', value: 'Notice Sent:good', icon: CircleCheckBig, severity: 'good' as Severity },
  { label: 'In Cure', value: 'In Cure:warning', icon: Clock, severity: 'warning' as Severity },
  { label: 'Expired', value: 'Expired:critical', icon: TriangleAlert, severity: 'critical' as Severity },
  { label: 'Fine Issued', value: 'Fine Issued:critical', icon: TriangleAlert, severity: 'critical' as Severity },
  { label: 'Flagged', value: 'Flagged:warning', icon: Clock, severity: 'warning' as Severity },
  { label: 'Closed', value: 'Closed:good', icon: CircleCheckBig, severity: 'good' as Severity },
  { label: 'Void', value: 'Void:good', icon: CircleCheckBig, severity: 'good' as Severity },
]
// __STATUSES_BLOCK_END__
