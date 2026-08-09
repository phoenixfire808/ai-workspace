import type { ApprovalItem } from "../lib/library-types";

export default function ApprovalReview({ title, approvals, onApprove, onCancel }: { title: string; approvals: ApprovalItem[]; onApprove: () => void; onCancel: () => void }) {
  return <div className="approval-backdrop" role="dialog" aria-modal="true" aria-label="Approval review">
    <section className="approval-review">
      <span className="eyebrow">REVIEW BEFORE RUN</span><h2>{title}</h2>
      <p>These protected actions will be approved together for this exact run. Any graph or argument change invalidates the review.</p>
      <div className="approval-items">{approvals.map((item) => <div key={item.resource_id}><strong>{item.label}</strong><small>{item.scope} · {item.resource_id}</small></div>)}</div>
      <div className="approval-actions"><button className="button button-quiet" type="button" onClick={onCancel}>Cancel</button><button className="button button-primary" type="button" onClick={onApprove}>Approve all and run</button></div>
    </section>
  </div>;
}
