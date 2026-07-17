import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideRouter } from '@angular/router';
import { providePrimeNG } from 'primeng/config';

import { routes } from './app.routes';
import {provideHttpClient, withInterceptors} from "@angular/common/http";
import { Noir } from "../app-theme";
import {MessageService} from "primeng/api";
import {errorInterceptor} from "./core/interceptors";

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes),
    provideHttpClient(withInterceptors([errorInterceptor])),
    providePrimeNG({
      theme: {
        preset: Noir
      }
    }),
    MessageService
  ]
};
