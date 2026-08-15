import { CloneRepositoryForm } from "@/components/repository/clone-repository-dialog";
import { RepositoryList } from "@/components/repository/repository-list";

export default function DashboardPage() {
  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 p-4 sm:p-6">
      <div>
        <h1 className="text-xl font-semibold">Dashboard</h1>
        <p className="mt-1 text-sm text-muted">
          Clone a public GitHub repository, then process it to start chatting with your codebase.
        </p>
      </div>

      <CloneRepositoryForm />

      <div>
        <h2 className="mb-3 text-sm font-semibold text-muted">Your repositories</h2>
        <RepositoryList />
      </div>
    </div>
  );
}
