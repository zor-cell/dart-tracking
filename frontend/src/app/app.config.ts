import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideRouter } from '@angular/router';
import { providePrimeNG } from 'primeng/config';

import { routes } from './app.routes';
import {provideHttpClient} from "@angular/common/http";
import { Noir } from "./app-theme";
import {MessageService} from "primeng/api";

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes),
    provideHttpClient(),
    providePrimeNG({
      theme: {
        preset: Noir
      }
    }),
    MessageService
  ]
};
