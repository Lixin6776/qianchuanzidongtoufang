import { ReportMessage } from "./ReportMessage";

export type MaterialAnalysis = {
  id: string;
  date: string;
  created_at: string;
  report_markdown: string;
};

export function MaterialAnalysisList({
  analyses,
  onGenerate
}: {
  analyses: MaterialAnalysis[];
  onGenerate?: () => void;
}) {
  return (
    <div className="material-analysis-list module-stack">
      <div className="module-toolbar">
        <div>
          <strong>素材投放日报</strong>
          <span>每天 08:00 自动生成；也可按需立即重跑。</span>
        </div>
        <button className="button-primary" type="button" onClick={onGenerate}>
          立即生成素材分析
        </button>
      </div>

      {analyses.length ? (
        analyses.map((analysis, index) => (
          <details className="material-analysis-item module-disclosure" key={analysis.id} open={index === 0}>
            <summary>
              <div>
                <strong>{analysis.date} 素材分析</strong>
                <span>消耗 · 素材 ROI · 点击率 · 转化率 · 动作分档</span>
              </div>
              <time>{new Date(analysis.created_at).toLocaleString("zh-CN")}</time>
            </summary>
            <div className="module-disclosure-body">
              <ReportMessage content={analysis.report_markdown} />
            </div>
          </details>
        ))
      ) : (
        <div className="module-empty-state">
          <strong>还没有素材分析</strong>
          <span>每天 08:00 自动生成，也可以点击上方按钮立即读取素材数据。</span>
        </div>
      )}
    </div>
  );
}
