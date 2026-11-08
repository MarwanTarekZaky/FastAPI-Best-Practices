import {
  Scanner,
  type IDetectedBarcode,
  type IScannerError,
} from "@yudiel/react-qr-scanner"
import { toast } from "sonner"

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

// Clear messages for the camera problems people actually hit
const CAMERA_ERRORS: Partial<Record<IScannerError["kind"], string>> = {
  "permission-denied": "Allow the camera for this site in the browser settings",
  "no-camera": "No camera found on this device",
  "in-use": "Another app is using the camera",
  "insecure-context": "The camera only works on https:// or localhost",
}

export function QrScannerDialog({
  open,
  onOpenChange,
  onCode,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onCode: (code: string) => void
}) {
  function handleScan(codes: IDetectedBarcode[]) {
    const value = codes[0]?.rawValue.trim() ?? ""
    if (/^\d{6}$/.test(value)) {
      onCode(value)
    } else {
      toast.error("This QR code isn't a delivery code")
    }
  }

  function handleError(error: IScannerError) {
    toast.error(CAMERA_ERRORS[error.kind] ?? `Camera error: ${error.message || error.kind}`)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Scan the delivery code</DialogTitle>
          <DialogDescription>
            Point the camera at the QR code in the client's email.
          </DialogDescription>
        </DialogHeader>
        {/* The dialog removes its content when closed, which turns the camera off */}
        <div className="overflow-hidden rounded-lg">
          <Scanner
            onScan={handleScan}
            onError={handleError}
            formats={["qr_code"]}
            // The back camera on phones, any camera on a computer. Sizes are only
            // "ideal": the library's default minimum (640x640) fails on many webcams
            constraints={{
              facingMode: "environment",
              width: { ideal: 1280 },
              height: { ideal: 720 },
            }}
            sound={false}
          />
        </div>
      </DialogContent>
    </Dialog>
  )
}
