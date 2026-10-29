import { ReportMessage } from "./ReportMessage";

export type LiveReview = {
  id: string;
  date: string;
  created_at: string;
  ended_at: string;
  report_markdown: string;
};

export function LiveReviewList({ reviews }: { reviews: LiveReview[] }) {
  if (!reviews.length) {
    return (
      <div className="module-empty-state">
        <strong>还没有直播复盘</strong>
        <span>直播结束后会自动生成复盘报告和下一场投放策略。</span>
      </div>
    );
  }

  return (
    <div className="live-review-list module-stack">
      {reviews.map((review, index) => (
        <details className="live-review-item module-disclosure" key={review.id} open={index === 0}>
          <summary>
            <div>
              <strong>{review.date} 直播复盘</strong>
              <span>场次复盘 · 问题归因 · 下场策略</span>
            </div>
            <time>{new Date(review.created_at).toLocaleString("zh-CN")}</time>
          </summary>
          <div className="module-disclosure-body">
            <ReportMessage content={review.report_markdown} />
          </div>
        </details>
      ))}
    </div>
  );
}
