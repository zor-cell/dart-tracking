import { Component, signal } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import {Button} from "primeng/button";

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, Button],
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss'
})
export class AppComponent {
  protected readonly title = signal('frontend');
}
