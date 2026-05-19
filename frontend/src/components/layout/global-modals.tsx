"use client";

import { useRouter } from "next/navigation";
import { Modal } from "@/components/ui/modal";
import { WorkOrderForm } from "@/components/work-orders/work-order-form";
import { useModals } from "@/stores/ui-store";
import type { WorkOrder } from "@/types";

export function GlobalModals() {
  const { activeModal, close } = useModals();
  const router = useRouter();

  const handleWorkOrderSuccess = (wo: WorkOrder) => {
    close();
    router.push(`/dashboard/work-orders/${wo.id}`);
  };

  return (
    <>
      <Modal
        open={activeModal === "create-work-order"}
        onClose={close}
        title="New Work Order"
        size="xl"
      >
        <WorkOrderForm onSuccess={handleWorkOrderSuccess} onCancel={close} />
      </Modal>
    </>
  );
}
