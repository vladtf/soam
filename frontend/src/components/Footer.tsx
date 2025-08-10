import React from 'react';
import { Container, Row, Col } from 'react-bootstrap';
import { FaGithub } from 'react-icons/fa';

const AppFooter: React.FC = () => {
    return (
        <Container className="pt-3 pb-4">
            <Row>
                <Col>
                    <footer className="bg-body-tertiary border-top border-body rounded-2 p-2 text-body">
                        <a href="https://github.com/vladtf/soam" target="_blank" rel="noopener noreferrer" className="text-decoration-none">
                            <FaGithub /><span className="ms-2">Repository</span>
                        </a>
                    </footer>
                </Col>
            </Row>
        </Container>
    );
};

export default AppFooter;
