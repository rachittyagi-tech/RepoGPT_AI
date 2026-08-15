import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { GitBranch } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useCloneRepository } from "@/hooks/use-repositories";
import { GITHUB_URL_PATTERN } from "@/utils/constants";

const schema = z.object({
  repoUrl: z
    .string()
    .trim()
    .min(1, "Enter a GitHub repository URL.")
    .regex(GITHUB_URL_PATTERN, "Must look like https://github.com/owner/repo"),
});

type FormValues = z.infer<typeof schema>;

/** The "paste a GitHub URL" entry point — the first thing a new user does. */
export function CloneRepositoryForm() {
  const cloneRepository = useCloneRepository();
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const onSubmit = handleSubmit(({ repoUrl }) => {
    cloneRepository.mutate(repoUrl, { onSuccess: () => reset() });
  });

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-1.5 sm:flex-row sm:items-start sm:gap-2">
      <div className="flex-1">
        <div className="relative">
          <GitBranch
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted"
            aria-hidden="true"
          />
          <Input
            {...register("repoUrl")}
            placeholder="https://github.com/owner/repository"
            className="pl-9 font-mono"
            aria-invalid={Boolean(errors.repoUrl)}
            aria-describedby={errors.repoUrl ? "repo-url-error" : undefined}
          />
        </div>
        {errors.repoUrl && (
          <p id="repo-url-error" className="mt-1 text-xs text-danger">
            {errors.repoUrl.message}
          </p>
        )}
      </div>
      <Button type="submit" loading={cloneRepository.isPending}>
        Clone repository
      </Button>
    </form>
  );
}
