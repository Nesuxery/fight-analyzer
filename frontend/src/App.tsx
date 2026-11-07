import { AppShell } from "./app/AppShell";
import { useRoute } from "./app/router";
import { StateView } from "./components/ui";
import { DemoProvider } from "./demo/DemoContext";
import { ProcessingScreen } from "./features/processing/ProcessingScreen";
import { ResultScreen } from "./features/result/ResultScreen";
import { SelectionScreen } from "./features/selection/SelectionScreen";
import { UploadScreen } from "./features/upload/UploadScreen";

export function App() {
  const route = useRoute();

  let screen;
  if (route.mode === "notFound") {
    screen = (
      <StateView tone="error" title="Sayfa bulunamadı"
                 action={<a className="btn btn--ghost" href="#/">Yükleme ekranına dön</a>}>
        <span className="mono">{route.path}</span> adresinde bir ekran yok.
      </StateView>
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
    <DemoProvider>
      <AppShell route={route}>{screen}</AppShell>
    </DemoProvider>
  );
}
