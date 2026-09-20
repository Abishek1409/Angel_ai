import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AuthService } from './auth.service';

@Component({
  selector: 'app-auth',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './auth.component.html',
  styleUrl: './auth.component.scss'
})
export class AuthComponent {
  mode: 'login' | 'register' = 'login';
  username = '';
  password = '';
  error = '';
  busy = false;

  constructor(private auth: AuthService) {}

  submit(): void {
    this.error = '';
    this.busy = true;
    const action = this.mode === 'login'
      ? this.auth.login(this.username, this.password)
      : this.auth.register(this.username, this.password);
    action.subscribe({
      error: (error) => {
        this.error = error.error?.error || 'Authentication failed.';
        this.busy = false;
      },
      complete: () => this.busy = false
    });
  }

  toggleMode(): void {
    this.mode = this.mode === 'login' ? 'register' : 'login';
    this.error = '';
  }
}