import { inject, Injectable } from '@angular/core';
import {MessageService} from "primeng/api";

@Injectable({
  providedIn: 'root',
})
export class NotificationService {
  private messageService = inject(MessageService);

  showSuccess(message: string, title = 'Success') {
    this.messageService.add({ severity: 'success', summary: title, detail: message });
  }

  showError(error: any, title = 'Error') {
    const status = error.status;

    let message: string = 'Unknown error';
    if (status === 0) {
      // backend unreachable
      message = 'Cannot connect to the server. Please check your internet connection or try again later'
    } else if (typeof error.error === 'string') {
      // text error
      message = error.error;
    } else if(Array.isArray(error.error)) {
      //array error
      message = error.error.map((err: any) => `• ${err}`).join('\n');
    } else if (error.error.message) {
      // JSON error
      message = error.error.message;
    } else if (error.message) {
      message = error.message;
    }

    this.messageService.add({ severity: 'error', summary: `${title} ${status !== undefined ? status : ''}`, detail: message });
  }

  showInfo(message: string, title = 'Information') {
    this.messageService.add({ severity: 'info', summary: title, detail: message });
  }

  showWarning(message: string, title = 'Warning') {
    this.messageService.add({ severity: 'warn', summary: title, detail: message });
  }
}