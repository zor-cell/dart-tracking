import { ApplicationConfig, inject, provideAppInitializer, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideRouter } from '@angular/router';
import { providePrimeNG } from 'primeng/config';

import { routes } from './app.routes';
import {provideHttpClient, withInterceptors} from "@angular/common/http";
import { Noir } from "../app-theme";
import {ConfirmationService, MessageService} from "primeng/api";
import {authInterceptor, errorInterceptor} from "./core/interceptors";
import { AnnouncerService } from './features/announcement/services/announcer.service';
import { CalibrationService } from './features/calibration/services/calibration.service';
import { GERMAN_TRANSLATION } from './core/config/primeng-translation';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes),
    provideHttpClient(withInterceptors([errorInterceptor, authInterceptor])),
    providePrimeNG({
      theme: {
        preset: Noir
      },
      translation: GERMAN_TRANSLATION,
    }),
    MessageService,
    ConfirmationService,
    // Listens from app start, so an announcer_state sent on join is never missed.
    provideAppInitializer(() => void inject(AnnouncerService)),
    provideAppInitializer(() => void inject(CalibrationService)),
  ]
};
