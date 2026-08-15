import { useQuery } from "@tanstack/react-query";
import { Moon, Sun } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useTheme } from "@/hooks/use-theme";
import { chatService } from "@/services/chat.service";
import { QUERY_KEYS } from "@/utils/constants";

export default function SettingsPage() {
  const { theme, setTheme } = useTheme();

  const { data: modelsData, isLoading } = useQuery({
    queryKey: QUERY_KEYS.chatModels,
    queryFn: () => chatService.listModels(),
  });

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6 p-4 sm:p-6">
      <div>
        <h1 className="text-xl font-semibold">Settings</h1>
        <p className="mt-1 text-sm text-muted">Appearance and backend connection status.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Appearance</CardTitle>
          <CardDescription>Choose how RepoGPT AI looks on this device.</CardDescription>
        </CardHeader>
        <CardContent className="flex gap-2">
          <Button variant={theme === "dark" ? "default" : "secondary"} onClick={() => setTheme("dark")}>
            <Moon className="h-4 w-4" /> Dark
          </Button>
          <Button variant={theme === "light" ? "default" : "secondary"} onClick={() => setTheme("light")}>
            <Sun className="h-4 w-4" /> Light
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Chat model</CardTitle>
          <CardDescription>The Gemini model currently configured on the backend.</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <Skeleton className="h-8 w-48" />
          ) : (
            <div className="flex flex-wrap gap-2">
              {modelsData?.models.map((model) => (
                <Badge key={model.name} variant={model.status === "active" ? "mint" : "danger"}>
                  {model.display_name} · {model.status}
                </Badge>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
