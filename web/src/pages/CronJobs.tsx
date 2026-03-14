import { useState } from "react";
import { useTranslation } from "react-i18next";
import {
  useCronJobs,
  useCreateCronJob,
  useUpdateCronJob,
  useDeleteCronJob,
  useToggleCronJob,
  type CronJob,
  type CronJobRequest,
  type CronSchedule,
} from "../hooks/useCron";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Switch } from "../components/ui/switch";
import { Textarea } from "../components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "../components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../components/ui/table";
import { ConfirmDialog } from "../components/shared/ConfirmDialog";
import { Skeleton } from "../components/ui/skeleton";
import { Plus, Pencil, Trash2 } from "lucide-react";
import { formatDate } from "../lib/utils";

const defaultSchedule: CronSchedule = { minute: "*", hour: "*", day: "*", month: "*", weekday: "*" };

function CronForm({
  initial,
  onSave,
  onClose,
}: {
  initial?: CronJob;
  onSave: (data: CronJobRequest) => void;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const [name, setName] = useState(initial?.name ?? "");
  const [sched, setSched] = useState<CronSchedule>(initial?.schedule ?? defaultSchedule);
  const [message, setMessage] = useState(initial?.payload.message ?? "");
  const [deliver, setDeliver] = useState(initial?.payload.deliver ?? false);
  const [channel, setChannel] = useState(initial?.payload.channel ?? "");
  const [to, setTo] = useState(initial?.payload.to ?? "");
  const [enabled, setEnabled] = useState(initial?.enabled ?? true);

  const handleSave = () => {
    onSave({
      name,
      enabled,
      schedule: sched,
      payload: { message, deliver, channel, to },
    });
  };

  const schedField = (f: keyof CronSchedule) => (
    <div className="space-y-1">
      <Label className="text-xs">{t(`cron.${f}`)}</Label>
      <Input
        className="font-mono text-sm h-8"
        value={sched[f]}
        onChange={(e) => setSched((p) => ({ ...p, [f]: e.target.value }))}
      />
    </div>
  );

  return (
    <>
      <div className="space-y-4 py-2">
        <div className="space-y-1">
          <Label>{t("cron.name")}</Label>
          <Input value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div>
          <Label className="mb-2 block">{t("cron.schedule")}</Label>
          <div className="grid grid-cols-5 gap-2">
            {(["minute", "hour", "day", "month", "weekday"] as (keyof CronSchedule)[]).map((f) => schedField(f))}
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            Current: <code className="font-mono">{`${sched.minute} ${sched.hour} ${sched.day} ${sched.month} ${sched.weekday}`}</code>
          </p>
        </div>
        <div className="space-y-1">
          <Label>{t("cron.message")}</Label>
          <Textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            rows={3}
          />
        </div>
        <div className="flex items-center gap-3">
          <Switch checked={deliver} onCheckedChange={setDeliver} id="deliver" />
          <Label htmlFor="deliver">Deliver to channel</Label>
        </div>
        {deliver && (
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label>Channel</Label>
              <Input value={channel} onChange={(e) => setChannel(e.target.value)} placeholder="telegram" />
            </div>
            <div className="space-y-1">
              <Label>To</Label>
              <Input value={to} onChange={(e) => setTo(e.target.value)} placeholder="chat_id" />
            </div>
          </div>
        )}
        <div className="flex items-center gap-3">
          <Switch checked={enabled} onCheckedChange={setEnabled} id="enabled" />
          <Label htmlFor="enabled">{enabled ? t("cron.enabled") : t("cron.disabled")}</Label>
        </div>
      </div>
      <DialogFooter>
        <Button variant="outline" onClick={onClose}>{t("common.cancel")}</Button>
        <Button onClick={handleSave} disabled={!name || !message}>{t("cron.save")}</Button>
      </DialogFooter>
    </>
  );
}

export default function CronJobs() {
  const { t } = useTranslation();
  const { data: jobs, isLoading } = useCronJobs();
  const create = useCreateCronJob();
  const update = useUpdateCronJob();
  const del = useDeleteCronJob();
  const toggle = useToggleCronJob();

  const [mode, setMode] = useState<"create" | "edit" | null>(null);
  const [editTarget, setEditTarget] = useState<CronJob | null>(null);
  const [delTarget, setDelTarget] = useState<string | null>(null);

  const handleSave = (data: CronJobRequest) => {
    if (mode === "create") {
      create.mutate(data);
    } else if (editTarget) {
      update.mutate({ id: editTarget.id, ...data });
    }
    setMode(null);
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button size="sm" onClick={() => { setEditTarget(null); setMode("create"); }}>
          <Plus className="mr-2 h-4 w-4" />
          {t("cron.add")}
        </Button>
      </div>

      {isLoading ? (
        <div className="space-y-2">{[...Array(3)].map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}</div>
      ) : (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("cron.name")}</TableHead>
                <TableHead>{t("cron.schedule")}</TableHead>
                <TableHead>{t("cron.nextRun")}</TableHead>
                <TableHead>{t("common.status")}</TableHead>
                <TableHead className="w-28 text-right">{t("common.actions")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {jobs?.map((j) => {
                const schedStr = `${j.schedule.minute} ${j.schedule.hour} ${j.schedule.day} ${j.schedule.month} ${j.schedule.weekday}`;
                return (
                  <TableRow key={j.id}>
                    <TableCell className="font-medium">{j.name}</TableCell>
                    <TableCell className="font-mono text-xs">{schedStr}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {j.next_run ? formatDate(j.next_run) : "-"}
                    </TableCell>
                    <TableCell>
                      <Badge variant={j.enabled ? "default" : "secondary"}>
                        {j.enabled ? t("cron.enabled") : t("cron.disabled")}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right space-x-1">
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 px-2 text-xs"
                        onClick={() => toggle.mutate({ id: j.id, enabled: !j.enabled })}
                      >
                        {j.enabled ? t("cron.disable") : t("cron.enable")}
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-7 w-7"
                        onClick={() => { setEditTarget(j); setMode("edit"); }}
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-7 w-7 text-destructive"
                        onClick={() => setDelTarget(j.id)}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </TableCell>
                  </TableRow>
                );
              })}
              {(!jobs || jobs.length === 0) && (
                <TableRow>
                  <TableCell colSpan={5} className="text-center text-muted-foreground">{t("common.noData")}</TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      )}

      <Dialog open={!!mode} onOpenChange={(v) => !v && setMode(null)}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>{mode === "create" ? t("cron.add") : t("cron.edit")}</DialogTitle>
          </DialogHeader>
          <CronForm
            initial={editTarget ?? undefined}
            onSave={handleSave}
            onClose={() => setMode(null)}
          />
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={!!delTarget}
        title={t("cron.delete")}
        description={t("cron.deleteConfirm")}
        destructive
        onConfirm={() => { if (delTarget) del.mutate(delTarget); setDelTarget(null); }}
        onCancel={() => setDelTarget(null)}
      />
    </div>
  );
}
