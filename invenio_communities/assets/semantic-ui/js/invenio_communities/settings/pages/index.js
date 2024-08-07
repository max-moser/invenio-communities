import { CommunityPagesForm } from "./CommunityPagesForm";
import ReactDOM from "react-dom";
import React from "react";

const domContainer = document.getElementById("community-settings-pages");
const community = JSON.parse(domContainer.dataset.community);

ReactDOM.render(<CommunityPagesForm community={community} />, domContainer);
