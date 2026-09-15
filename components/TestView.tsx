"use client";

import { useEffect, useState } from "react";
import { Site, Worker, TestQuestion, TestAttempt, getTestQuestions, submitTest } from "@/lib/api";
import { Loader2, CheckCircle2, XCircle, AlertCircle, MapPin, User, ChevronLeft } from "lucide-react";

interface Props {
  site: Site;
  worker: Worker;
  onDone: () => void;
}

export default function TestView({ site, worker, onDone }: Props) {
  const [questions, setQuestions] = useState<TestQuestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<TestAttempt | null>(null);

  useEffect(() => {
    getTestQuestions(worker.id)
      .then(setQuestions)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [worker.id]);

  function handleSelect(questionId: number, option: string) {
    setAnswers((prev) => ({ ...prev, [questionId]: option }));
  }

  async function handleSubmit() {
    if (Object.keys(answers).length < questions.length) {
      if (!confirm("You have unanswered questions. Submit anyway?")) {
        return;
      }
    }
    setSubmitting(true);
    setError(null);
    try {
      const formattedAnswers = Object.entries(answers).map(([qId, ans]) => ({
        question_id: parseInt(qId),
        answer: ans,
      }));
      const res = await submitTest(worker.id, site.id, formattedAnswers);
      setResult(res);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <div className="picker-container" style={{ textAlign: "center", padding: "60px 20px" }}>
        <Loader2 size={32} className="spin" style={{ margin: "0 auto 16px", color: "var(--primary)" }} />
        <p>Loading test questions...</p>
      </div>
    );
  }

  if (error && !questions.length) {
    return (
      <div className="picker-container">
        <div className="picker-error"><AlertCircle size={16} /> {error}</div>
        <button className="btn-outline" onClick={onDone}>Go Back</button>
      </div>
    );
  }

  if (result) {
    const isPass = result.passed;
    return (
      <div className="picker-container" style={{ textAlign: "center", padding: "60px 20px" }}>
        {isPass ? (
          <CheckCircle2 size={64} style={{ margin: "0 auto 20px", color: "var(--success)" }} />
        ) : (
          <XCircle size={64} style={{ margin: "0 auto 20px", color: "var(--danger)" }} />
        )}
        <h2 style={{ fontSize: 28, marginBottom: 8, color: isPass ? "var(--success)" : "var(--danger)" }}>
          {isPass ? "PASSED" : "FAILED"}
        </h2>
        <p style={{ fontSize: 18, marginBottom: 24 }}>
          Score: {result.score} / {result.total} ({(result.score / result.total * 100).toFixed(0)}%)
        </p>
        <p style={{ color: "var(--text-secondary)", marginBottom: 32 }}>
          Passing requirement is 33% (17 correct).
        </p>
        <button className="btn-primary" onClick={onDone}>Return to Dashboard</button>
      </div>
    );
  }

  const answeredCount = Object.keys(answers).length;

  return (
    <div className="picker-container">
      {/* Header */}
      <div className="picker-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16 }}>
        <div>
          <h2>Safety Knowledge Test</h2>
          <p>Read the questions to the worker and record their answers.</p>
        </div>
        <button className="btn-ghost" onClick={onDone}><ChevronLeft size={16} /> Back</button>
      </div>
      
      <div className="context-bar" style={{ marginBottom: 24 }}>
        <span className="context-pill"><MapPin size={13} />{site.name}</span>
        <span className="context-pill"><User size={13} />{worker.full_name}</span>
      </div>

      {error && <div className="picker-error">{error}</div>}

      {/* Progress */}
      <div style={{ marginBottom: 24, fontSize: 14, fontWeight: 600, color: "var(--text-secondary)" }}>
        Answered: {answeredCount} / {questions.length}
      </div>

      {/* Questions list */}
      <div style={{ display: "flex", flexDirection: "column", gap: 24, maxHeight: "60vh", overflowY: "auto", paddingRight: 16 }}>
        {questions.map((q, idx) => (
          <div key={q.id} style={{ background: "var(--background)", padding: 20, borderRadius: "var(--radius-md)", border: "1px solid var(--border)" }}>
            <h3 style={{ fontSize: 15, marginBottom: 16, lineHeight: 1.5 }}>
              <span style={{ color: "var(--text-secondary)", marginRight: 8 }}>{idx + 1}.</span>
              {q.text}
            </h3>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {["A", "B", "C", "D"].map((optKey) => {
                const text = q.options[optKey as keyof typeof q.options];
                const isSelected = answers[q.id] === optKey;
                return (
                  <label key={optKey} style={{ 
                    display: "flex", alignItems: "center", gap: 12, 
                    padding: "10px 16px", borderRadius: "var(--radius-sm)", 
                    border: `1.5px solid ${isSelected ? "var(--primary)" : "var(--border)"}`,
                    background: isSelected ? "#eff6ff" : "var(--surface)",
                    cursor: "pointer", transition: "all 0.15s"
                  }}>
                    <input 
                      type="radio" 
                      name={`q-${q.id}`} 
                      checked={isSelected}
                      onChange={() => handleSelect(q.id, optKey)}
                      style={{ width: 16, height: 16 }}
                    />
                    <span style={{ fontWeight: 600, color: "var(--text-secondary)", width: 20 }}>{optKey}.</span>
                    <span style={{ fontSize: 14 }}>{text}</span>
                  </label>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      <div className="picker-actions" style={{ marginTop: 24, borderTop: "1px solid var(--border)", paddingTop: 20 }}>
        <button 
          className="btn-primary" 
          onClick={handleSubmit}
          disabled={submitting || answeredCount === 0}
        >
          {submitting ? <><Loader2 size={16} className="spin" /> Submitting...</> : "Submit Test"}
        </button>
      </div>
    </div>
  );
}
