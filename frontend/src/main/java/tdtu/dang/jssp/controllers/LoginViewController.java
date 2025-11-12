package tdtu.dang.jssp.controllers;

import javafx.fxml.FXML;
import javafx.scene.control.Button;
import javafx.scene.control.Label;
import javafx.scene.control.PasswordField;
import javafx.scene.control.TextField;
import javafx.scene.input.KeyCode;
import javafx.scene.input.KeyEvent;
import javafx.scene.layout.VBox;
import tdtu.dang.jssp.MainApp;
import tdtu.dang.jssp.services.ApiClient;
import java.io.IOException;

public class LoginViewController {

    @FXML private VBox loginContainer;
    @FXML private TextField usernameField;
    @FXML private PasswordField passwordField;
    @FXML private Button loginButton;
    @FXML private Label errorLabel;

    private ApiClient apiClient;
    private MainApp mainApp;

    @FXML
    public void initialize() {
        this.apiClient = new ApiClient();
        errorLabel.setVisible(false);
        errorLabel.setManaged(false);
    }

    // This method is called by MainApp to link them
    public void setMainApp(MainApp mainApp) {
        this.mainApp = mainApp;
    }

    // This method allows MainApp to pass the shared ApiClient
    public void setApiClient(ApiClient apiClient) {
        this.apiClient = apiClient;
    }

    @FXML
    private void handleLoginButton() {
        String username = usernameField.getText();
        String password = passwordField.getText();

        if (username.isEmpty() || password.isEmpty()) {
            showError("Username and password are required.");
            return;
        }

        try {
            // Try to log in
            String loggedInUsername = apiClient.login(username, password);
            
            if (loggedInUsername != null) {
                // SUCCESS
                hideError();
                // Tell MainApp to switch scenes
                mainApp.showMainView(loggedInUsername, this.apiClient);
            } else {
                // Failure (ApiCClient returns null on 401)
                showError("Invalid username or password.");
            }
        } catch (IOException | InterruptedException e) {
            // Failure (Network error, server down, etc.)
            showError(e.getMessage());
            e.printStackTrace();
        }
    }

    @FXML
    private void handleLoginKeyPress(KeyEvent event) {
        if (event.getCode() == KeyCode.ENTER) {
            handleLoginButton();
        }
    }

    private void showError(String message) {
        errorLabel.setText(message);
        errorLabel.setVisible(true);
        errorLabel.setManaged(true);
    }

    private void hideError() {
        errorLabel.setVisible(false);
        errorLabel.setManaged(false);
    }

    // This is called by MainApp when the user logs out
    public void clearPassword() {
        passwordField.clear();
    }
}