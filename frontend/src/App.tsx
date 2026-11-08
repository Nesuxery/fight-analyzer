import { AppShell } from "./app/AppShell";
import { useRoute } from "./app/router";
import { DemoProvider } from "./demo/DemoContext";
import { ProcessingScreen } from "./features/processing/ProcessingScreen";
import { ResultScreen } from "./features/result/ResultScreen";
import { SelectionScreen } from "./features/selection/SelectionScreen";
import { UploadScreen } from "./features/upload/UploadScreen";
import { COMMON_LABELS } from "./labels";
import { ButtonLink, EmptyState, ToastProvider } from "./ui";

export function App() {
  const route = useRoute();

  let screen;
  if (route.mode === "notFound") {
    screen = (
      <EmptyState tone="error" title={COMMON_LABELS.notFoundTitle}
                  action={<ButtonLink href="#/">{COMMON_LABELS.backToUpload}</ButtonLink>}>
        <span className="mono">{route.path}</span> {COMMON_LABELS.notFoundText}
      </EmptyState>
    );
  } else {
    const demo = route.mode === "demo";
    const jobId = route.mode === "analysis" && route.screen !== "upload" ? route.jobId : undefined;
    // Keyed so each screen/job starts with fresh state and polling.
    const key = `${route.mode}:${route.screen}:${jobId ?? ""}`;
    switch (route.screen) {
      case "upload":
        screen = <UploadScreen key={key} demo={demo} />;
        break;
      case "processing":
        screen = <ProcessingScreen key={key} demo={demo} jobId={jobId} />;
        break;
      case "select":
        screen = <SelectionScreen key={key} demo={demo} jobId={jobId}
                                  params={route.mode === "analysis" && route.screen === "select" ? route.params : undefined} />;
        break;
      case "result":
        screen = <ResultScreen key={key} demo={demo} jobId={jobId} />;
        break;
    }
  }

  return (
    <ToastProvider>
      <DemoProvider>
        <AppShell route={route}>{screen}</AppShell>
      </DemoProvider>
    </ToastProvider>
  );
}
